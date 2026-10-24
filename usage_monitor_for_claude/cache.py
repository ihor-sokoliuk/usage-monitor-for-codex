"""
Usage Cache
============

Thread-safe cache for provider data - the single source of truth for usage
state. All refresh requests go through ``UsageCache.update()``, whose lock
and cooldown preserve the upstream polling and backoff invariants.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .api import fetch_provider_data, refresh_profile as adapter_refresh_profile, shutdown_transport
from .app_server import TransportError
from .codex_cli import CliUpdateResult, update_cli
from .i18n import T
from .settings import MAX_BACKOFF, POLL_FAST, POLL_INTERVAL

__all__ = ['CacheSnapshot', 'MANUAL_REFRESH_INTERVAL', 'RESET_BUFFER', 'UpdateResult', 'UsageCache']

log = logging.getLogger(__name__)
MANUAL_REFRESH_INTERVAL = 30
# Allow the new quota window to propagate before the confirming poll.
RESET_BUFFER = 5


@dataclass(frozen=True)
class CacheSnapshot:
    """Immutable, consistent snapshot of cache state for the popup."""

    usage: dict[str, Any]
    profile: dict[str, Any] | None
    last_success_time: float | None
    refreshing: bool
    last_error: str | None
    version: int
    manual_refresh_reason: str | None = None
    manual_refresh_retry_at: float | None = None


@dataclass(frozen=True)
class UpdateResult:
    """Result of a ``UsageCache.update()`` call.

    Attributes
    ----------
    data : dict or None
        Provider response dict, or ``None`` when the call was skipped
        (lock held or cooldown active).
    """

    data: dict[str, Any] | None


class UsageCache:
    """Thread-safe cache managing provider data, cooldown, and error state.

    All callers (poll loop, popup) go through ``update()`` instead of
    calling the provider adapter directly.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._profile_lock = threading.Lock()
        self._usage: dict[str, Any] = {}
        self._profile: dict[str, Any] | None = None
        self._last_success_time: float | None = None
        self._refreshing = False
        self._last_error: str | None = None
        self._version = 0
        self._consecutive_errors = 0
        self._recovery_attempted = False
        self._rate_limit_until: float = 0
        self._last_attempt_monotonic: float | None = None

    # Public properties

    @property
    def usage(self) -> dict[str, Any]:
        """Last successful usage data (empty dict before first success)."""
        return self._usage

    @property
    def profile(self) -> dict[str, Any] | None:
        return self._profile

    @property
    def last_success_time(self) -> float | None:
        return self._last_success_time

    @property
    def refreshing(self) -> bool:
        return self._refreshing

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def version(self) -> int:
        """Change counter - incremented on every state change."""
        return self._version

    @property
    def consecutive_errors(self) -> int:
        return self._consecutive_errors

    @property
    def rate_limit_remaining(self) -> float:
        """Seconds remaining in the rate-limit backoff window, or 0."""
        return max(self._rate_limit_until - time.time(), 0)

    @property
    def snapshot(self) -> CacheSnapshot:
        """Return a consistent snapshot for the popup to display."""
        with self._state_lock:
            reason, retry_at = self._manual_refresh_state(time.time())
            return CacheSnapshot(
                usage=self._usage,
                profile=self._profile,
                last_success_time=self._last_success_time,
                refreshing=self._refreshing,
                last_error=self._last_error,
                version=self._version,
                manual_refresh_reason=reason,
                manual_refresh_retry_at=retry_at,
            )

    # Public methods

    def ensure_profile(self, *, bypass_rate_limit: bool = False) -> None:
        """Fetch the account profile if it has not been loaded yet.

        Profile-only reads share ``_lock`` with combined usage updates, so
        their provider result and state commit cannot be overtaken by an
        older combined operation. A rate-limit backoff still suppresses the
        popup cold path unless explicitly bypassed.

        Parameters
        ----------
        bypass_rate_limit : bool
            When True, probe the profile even during the retained provider
            backoff window. Used for immediate account-switch checks, where
            identity confirmation must not wait on stale throttling state.
        """
        if self._profile is not None:
            return

        with self._profile_lock:
            if self._profile is not None:
                return

            # Respect the retained rate-limit backoff window. A failed profile
            # fetch leaves _profile as None, so without this guard every popup
            # open would retry while the provider is already backing off.
            if not bypass_rate_limit and time.time() < self._rate_limit_until:
                log.debug('ensure_profile skipped (rate-limit backoff, %.0fs remaining)', self._rate_limit_until - time.time())
                return

            log.info('refresh_profile (cold path) started')
            with self._lock:
                if self._profile is not None:
                    return
                self._store_profile(adapter_refresh_profile())

    def refresh_profile(self) -> None:
        """Fetch fresh account state independently of the usage cooldown."""
        with self._profile_lock:
            with self._lock:
                log.info('refresh_profile started')
                self._store_profile(adapter_refresh_profile())

    def update_codex_cli(self) -> CliUpdateResult:
        """Stop provider operations and run the official Codex self-updater."""
        with self._lock:
            try:
                shutdown_transport()
            except TransportError:
                log.warning('codex update deferred; child exit is unconfirmed')
                return CliUpdateResult(False, False, '', '', 'App-server shutdown incomplete')
            return update_cli()

    def update(self, *, manual: bool = False, force: bool = False) -> UpdateResult:
        """Fetch usage data with lock and cooldown protection.

        Parameters
        ----------
        manual : bool
            Wait for an in-progress usage operation. Allow an early fetch
            only outside the manual floor and reset window, retaining backoff.
        force : bool
            When True, bypass the ``POLL_FAST`` cooldown and retained
            rate-limit backoff for this single fetch. Used only after a
            confirmed account switch. The update lock is still honored, so
            concurrent fetches never run.

        Returns
        -------
        UpdateResult
            Contains the provider response dict (``data``), or ``None``
            when the call was skipped.
        """
        if not self._lock.acquire(blocking=manual):
            log.debug('update skipped (another update in progress)')
            return UpdateResult(data=None)

        try:
            return self._update_locked(manual=manual, force=force)
        finally:
            self._lock.release()

    # Private helpers

    def _manual_refresh_state(self, now: float) -> tuple[str | None, float | None]:
        """Return a withheld manual request's reason and retry timestamp.

        Called while holding ``_state_lock``. A monotonic completion clock
        keeps wall-clock adjustments from shortening the manual floor.
        """
        if now < self._rate_limit_until:
            return 'backoff', self._rate_limit_until

        if self._last_success_time is not None:
            resets = []
            for entry in self._usage.values():
                if not isinstance(entry, dict) or not entry.get('resets_at'):
                    continue
                try:
                    reset = datetime.fromisoformat(entry['resets_at'])
                    if reset.utcoffset() is None:
                        continue
                    reset_at = reset.timestamp()
                except (TypeError, ValueError, OverflowError):
                    continue
                if -RESET_BUFFER < reset_at - now < POLL_FAST:
                    resets.append(reset_at + RESET_BUFFER)
            if resets:
                return 'reset', max(resets)

        if self._last_attempt_monotonic is not None:
            elapsed = max(0.0, time.monotonic() - self._last_attempt_monotonic)
        elif self._last_success_time is not None:
            elapsed = max(0.0, now - self._last_success_time)
        else:
            return None, None
        remaining = MANUAL_REFRESH_INTERVAL - elapsed
        if remaining > 0:
            return 'cooldown', now + remaining
        return None, None

    def _update_locked(self, *, manual: bool = False, force: bool = False) -> UpdateResult:
        """Execute the actual update while holding ``_lock``."""
        now = time.time()
        if self._last_success_time is not None and now < self._last_success_time:
            self._last_success_time = now - POLL_FAST
        if self._rate_limit_until - now > MAX_BACKOFF:
            self._rate_limit_until = now + MAX_BACKOFF

        if not (force or manual) and self._last_success_time is not None and time.time() - self._last_success_time < POLL_FAST:
            log.debug('update skipped (cooldown, %.0fs remaining)', POLL_FAST - (time.time() - self._last_success_time))
            return UpdateResult(data=None)

        if not force and time.time() < self._rate_limit_until:
            log.debug('update skipped (rate-limit backoff, %.0fs remaining)', self._rate_limit_until - time.time())
            return UpdateResult(data=None)

        if manual and not force:
            with self._state_lock:
                reason, _retry_at = self._manual_refresh_state(now)
            if reason is not None:
                log.debug('manual update deferred (%s)', reason)
                return UpdateResult(data=None)

        with self._state_lock:
            self._refreshing = True
            self._version += 1

        try:
            return self._fetch_and_process()
        except Exception:
            log.exception('unexpected provider update failure')
            data = {'error': T['connection_error']}
            self._record_error_state(data, None, False)
            return UpdateResult(data=data)
        finally:
            with self._state_lock:
                self._last_attempt_monotonic = time.monotonic()
                self._version += 1

    def _fetch_and_process(self) -> UpdateResult:
        """Fetch usage and profile together and process one provider result."""
        with self._state_lock:
            allow_recovery = not self._recovery_attempted
        log.info('fetch_provider_data started (allow_recovery=%s)', allow_recovery)
        result = fetch_provider_data(allow_recovery=allow_recovery)
        data = result.usage

        if 'error' in data:
            delay = self._record_error_state(data, result.profile, result.recovery_attempted)
            if delay is not None:
                log.warning('fetch_provider_data -> rate limited, backoff %.0fs', delay)
            else:
                log.warning('fetch_provider_data -> error: %s', data['error'])
            return UpdateResult(data=data)

        pct_5h = (data.get('five_hour') or {}).get('utilization')
        pct_7d = (data.get('seven_day') or {}).get('utilization')
        log.info('fetch_provider_data -> OK (5h: %s%%, 7d: %s%%)',
                 pct_5h if pct_5h is not None else '?', pct_7d if pct_7d is not None else '?')
        self._record_success(data, result.profile)
        return UpdateResult(data=data)

    def _record_error_state(self, data: dict[str, Any], profile: dict[str, Any] | None,
                            recovery_attempted: bool) -> float | None:
        """Apply an error cycle atomically and return its backoff delay."""
        delay = None
        with self._state_lock:
            self._consecutive_errors += 1
            error = data['error']
            server_msg = data.get('server_message')
            if server_msg:
                error += f'\n{server_msg}'
            self._last_error = error

            if data.get('rate_limited'):
                retry_after = data.get('retry_after')
                if retry_after is not None and retry_after > 0:
                    delay = min(max(retry_after, POLL_INTERVAL), MAX_BACKOFF)
                else:
                    delay = min(POLL_INTERVAL * (2 ** max(self._consecutive_errors - 1, 0)), MAX_BACKOFF)
                self._rate_limit_until = time.time() + delay

            self._store_profile_locked(profile)
            if recovery_attempted:
                self._recovery_attempted = True
            self._refreshing = False
            self._version += 1
        return delay

    def _record_success(self, data: dict[str, Any], profile: dict[str, Any] | None) -> None:
        """Apply common state updates after a successful provider response."""
        # _usage is always reassigned (never mutated in place), so existing
        # CacheSnapshot references remain valid after this update.
        with self._state_lock:
            self._consecutive_errors = 0
            self._last_error = None
            self._last_success_time = time.time()
            self._rate_limit_until = 0
            self._recovery_attempted = False
            self._store_profile_locked(profile)
            self._usage = data
            self._refreshing = False
            self._version += 1

    def _store_profile(self, profile: dict[str, Any] | None) -> None:
        """Store a profile result: dict replaces and None preserves."""
        if profile is None:
            return
        with self._state_lock:
            self._store_profile_locked(profile)
            self._version += 1

    def _store_profile_locked(self, profile: dict[str, Any] | None) -> None:
        """Store a profile while holding the state lock."""
        if profile is None:
            return
        previous_uuid = (self._profile or {}).get('account', {}).get('uuid') if isinstance(self._profile, dict) else None
        new_uuid = profile.get('account', {}).get('uuid') if profile else None
        if new_uuid != previous_uuid:
            self._recovery_attempted = False
        self._profile = profile
