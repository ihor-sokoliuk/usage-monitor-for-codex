"""
Cache Tests
===========

Unit tests for UsageCache locking, cooldown, backoff, atomic state, provider
profile semantics, and recovery episodes.
"""
from __future__ import annotations

import threading
import time
import unittest
from unittest.mock import patch

from usage_monitor_for_claude.api import ProviderFetchResult
from usage_monitor_for_claude.cache import CacheSnapshot, UpdateResult, UsageCache
from usage_monitor_for_claude.codex_cli import CliUpdateResult

_SUCCESS_DATA = {'five_hour': {'utilization': 42.0, 'resets_at': ''}}
_ERROR_DATA = {'error': 'server down'}
_SERVER_MSG_DATA = {'error': 'HTTP 429', 'server_message': 'Rate limited.'}
_PROFILE_A = {
    'account': {'email': 'a@x.com', 'uuid': 'chatgpt:a@x.com'},
    'organization': {'organization_type': 'plus'},
}
_PROFILE_B = {
    'account': {'email': 'b@x.com', 'uuid': 'chatgpt:b@x.com'},
    'organization': {'organization_type': 'plus'},
}


def pfr(usage, profile=None, recovery=False):
    return ProviderFetchResult(usage=usage, profile=profile, recovery_attempted=recovery)


def _make_cache() -> UsageCache:
    return UsageCache()


class TestLockBehavior(unittest.TestCase):
    def test_concurrent_update_skipped(self):
        cache = _make_cache()
        cache._lock.acquire()
        try:
            result = cache.update()
        finally:
            cache._lock.release()
        self.assertIsNone(result.data)

    def test_update_succeeds_when_lock_free(self):
        cache = _make_cache()
        with patch('usage_monitor_for_claude.cache.fetch_provider_data', return_value=pfr(_SUCCESS_DATA)):
            self.assertEqual(cache.update().data, _SUCCESS_DATA)

    def test_lock_released_on_exception(self):
        cache = _make_cache()
        with patch('usage_monitor_for_claude.cache.fetch_provider_data', side_effect=RuntimeError('boom')), \
             patch('usage_monitor_for_claude.cache.log.exception') as logged:
            result = cache.update()
        self.assertIn('error', result.data)
        logged.assert_called_once()
        self.assertFalse(cache._lock.locked())

    def test_refreshing_reset_on_exception(self):
        cache = _make_cache()
        with patch('usage_monitor_for_claude.cache.fetch_provider_data', side_effect=RuntimeError('boom')):
            result = cache.update()
        self.assertIn('error', result.data)
        self.assertFalse(cache.refreshing)
        self.assertEqual(cache.last_error, result.data['error'])

    def test_successful_poll_can_follow_unexpected_failure(self):
        cache = _make_cache()
        with patch('usage_monitor_for_claude.cache.fetch_provider_data', side_effect=[RuntimeError('boom'), pfr(_SUCCESS_DATA)]):
            first = cache.update()
            second = cache.update()
        self.assertIn('error', first.data)
        self.assertEqual(second.data, _SUCCESS_DATA)
        self.assertEqual(cache.usage, _SUCCESS_DATA)


class TestCooldownBehavior(unittest.TestCase):
    def test_second_call_within_cooldown_skipped(self):
        cache = _make_cache()
        with patch('usage_monitor_for_claude.cache.fetch_provider_data', return_value=pfr(_SUCCESS_DATA)) as fetch:
            cache.update()
            result = cache.update()
        self.assertIsNone(result.data)
        fetch.assert_called_once()

    def test_call_after_cooldown_proceeds(self):
        cache = _make_cache()
        with patch('usage_monitor_for_claude.cache.fetch_provider_data', return_value=pfr(_SUCCESS_DATA)) as fetch, \
             patch('usage_monitor_for_claude.cache.time') as mock_time:
            mock_time.time.return_value = 1000.0
            cache.update()
            mock_time.time.return_value = 1121.0
            result = cache.update()
        self.assertIsNotNone(result.data)
        self.assertEqual(fetch.call_count, 2)

    def test_first_call_always_proceeds(self):
        cache = _make_cache()
        with patch('usage_monitor_for_claude.cache.fetch_provider_data', return_value=pfr(_SUCCESS_DATA)):
            self.assertIsNotNone(cache.update().data)

    def test_no_cooldown_after_error(self):
        cache = _make_cache()
        with patch('usage_monitor_for_claude.cache.fetch_provider_data', return_value=pfr(_ERROR_DATA)) as fetch:
            cache.update()
            cache.update()
        self.assertEqual(fetch.call_count, 2)

    def test_force_bypasses_cooldown(self):
        cache = _make_cache()
        with patch('usage_monitor_for_claude.cache.fetch_provider_data', return_value=pfr(_SUCCESS_DATA)) as fetch:
            cache.update()
            result = cache.update(force=True)
        self.assertIsNotNone(result.data)
        self.assertEqual(fetch.call_count, 2)

    @patch('usage_monitor_for_claude.cache.fetch_provider_data', return_value=pfr(_SUCCESS_DATA))
    @patch('usage_monitor_for_claude.cache.time')
    def test_backward_clock_jump_does_not_stall_cooldown(self, mock_time, fetch):
        cache = _make_cache()
        mock_time.time.return_value = 10000.0
        cache.update()
        fetch.reset_mock()

        mock_time.time.return_value = 6400.0
        result = cache.update()

        self.assertIsNotNone(result.data)
        fetch.assert_called_once()

    @patch('usage_monitor_for_claude.cache.fetch_provider_data', return_value=pfr(_SUCCESS_DATA))
    @patch('usage_monitor_for_claude.cache.time')
    def test_backward_clock_jump_caps_rate_limit_backoff(self, mock_time, _fetch):
        cache = _make_cache()
        cache._rate_limit_until = 10000.0
        mock_time.time.return_value = 5000.0

        cache.update()

        self.assertLessEqual(cache._rate_limit_until - 5000.0, 900)


class TestSuccessState(unittest.TestCase):
    def _updated(self):
        cache = _make_cache()
        with patch('usage_monitor_for_claude.cache.fetch_provider_data', return_value=pfr(_SUCCESS_DATA, _PROFILE_A)):
            cache.update()
        return cache

    def test_success_stores_usage_data(self):
        self.assertEqual(self._updated().usage, _SUCCESS_DATA)

    def test_success_sets_last_success_time(self):
        self.assertIsNotNone(self._updated().last_success_time)

    def test_success_clears_error(self):
        cache = _make_cache()
        cache._last_error = 'old'
        with patch('usage_monitor_for_claude.cache.fetch_provider_data', return_value=pfr(_SUCCESS_DATA)):
            cache.update()
        self.assertIsNone(cache.last_error)

    def test_success_resets_consecutive_errors(self):
        cache = _make_cache()
        cache._consecutive_errors = 3
        with patch('usage_monitor_for_claude.cache.fetch_provider_data', return_value=pfr(_SUCCESS_DATA)):
            cache.update()
        self.assertEqual(cache.consecutive_errors, 0)

    def test_success_clears_refreshing_flag(self):
        self.assertFalse(self._updated().refreshing)

    def test_success_increments_version_twice(self):
        self.assertEqual(self._updated().version, 2)


class TestErrorState(unittest.TestCase):
    def test_error_increments_consecutive_errors(self):
        cache = _make_cache()
        with patch('usage_monitor_for_claude.cache.fetch_provider_data', return_value=pfr(_ERROR_DATA)):
            cache.update()
        self.assertEqual(cache.consecutive_errors, 1)

    def test_error_sets_last_error(self):
        cache = _make_cache()
        with patch('usage_monitor_for_claude.cache.fetch_provider_data', return_value=pfr(_ERROR_DATA)):
            cache.update()
        self.assertEqual(cache.last_error, 'server down')

    def test_server_message_appended_to_last_error(self):
        cache = _make_cache()
        with patch('usage_monitor_for_claude.cache.fetch_provider_data', return_value=pfr(_SERVER_MSG_DATA)):
            cache.update()
        self.assertEqual(cache.last_error, 'HTTP 429\nRate limited.')

    @patch('usage_monitor_for_claude.cache.time.time', return_value=1000.0)
    def test_recovery_retry_rate_limit_arms_backoff_and_surfaces_429(self, _time):
        """A rate limit returned by the adapter's recovery retry is current state."""
        rate_limited = {'error': 'HTTP 429', 'rate_limited': True, 'retry_after': 300}
        cache = _make_cache()

        with patch('usage_monitor_for_claude.cache.fetch_provider_data', return_value=pfr(rate_limited, _PROFILE_A, True)):
            result = cache.update()

        self.assertEqual(result.data, rate_limited)
        self.assertEqual(cache.rate_limit_remaining, 300)
        self.assertEqual(cache.last_error, 'HTTP 429')

    def test_no_server_message_leaves_error_unchanged(self):
        cache = _make_cache()
        with patch('usage_monitor_for_claude.cache.fetch_provider_data', return_value=pfr({'error': 'HTTP 500'})):
            cache.update()
        self.assertEqual(cache.last_error, 'HTTP 500')

    def test_error_preserves_cached_usage(self):
        cache = _make_cache()
        cache._usage = _SUCCESS_DATA
        with patch('usage_monitor_for_claude.cache.fetch_provider_data', return_value=pfr(_ERROR_DATA)):
            cache.update()
        self.assertEqual(cache.usage, _SUCCESS_DATA)

    def test_error_clears_refreshing_flag(self):
        cache = _make_cache()
        with patch('usage_monitor_for_claude.cache.fetch_provider_data', return_value=pfr(_ERROR_DATA)):
            cache.update()
        self.assertFalse(cache.refreshing)

    def test_error_increments_version_twice(self):
        cache = _make_cache()
        with patch('usage_monitor_for_claude.cache.fetch_provider_data', return_value=pfr(_ERROR_DATA)):
            cache.update()
        self.assertEqual(cache.version, 2)


class TestRefreshingFlag(unittest.TestCase):
    def test_refreshing_true_during_provider_call(self):
        cache = _make_cache()
        observed = []

        def capture(allow_recovery=False):
            observed.append(cache.refreshing)
            return pfr(_SUCCESS_DATA)

        with patch('usage_monitor_for_claude.cache.fetch_provider_data', side_effect=capture):
            cache.update()
        self.assertEqual(observed, [True])


class TestRateLimitGuard(unittest.TestCase):
    def test_rate_limit_blocks_subsequent_call(self):
        cache = _make_cache()
        error = {'error': 'HTTP 429', 'rate_limited': True}
        with patch('usage_monitor_for_claude.cache.fetch_provider_data', return_value=pfr(error)) as fetch, \
             patch('usage_monitor_for_claude.cache.time') as mock_time:
            mock_time.time.return_value = 1000.0
            cache.update()
            mock_time.time.return_value = 1001.0
            self.assertIsNone(cache.update().data)
        fetch.assert_called_once()

    def test_force_bypasses_rate_limit_backoff(self):
        cache = _make_cache()
        error = {'error': 'HTTP 429', 'rate_limited': True}
        with patch('usage_monitor_for_claude.cache.fetch_provider_data') as fetch, \
             patch('usage_monitor_for_claude.cache.time') as mock_time:
            mock_time.time.return_value = 1000.0
            fetch.return_value = pfr(error)
            cache.update()
            fetch.return_value = pfr(_SUCCESS_DATA)
            mock_time.time.return_value = 1001.0
            result = cache.update(force=True)
        self.assertEqual(result.data, _SUCCESS_DATA)

    def test_rate_limit_expires(self):
        cache = _make_cache()
        error = {'error': 'HTTP 429', 'rate_limited': True}
        with patch('usage_monitor_for_claude.cache.fetch_provider_data') as fetch, \
             patch('usage_monitor_for_claude.cache.time') as mock_time:
            mock_time.time.return_value = 1000.0
            fetch.return_value = pfr(error)
            cache.update()
            fetch.return_value = pfr(_SUCCESS_DATA)
            mock_time.time.return_value = 1181.0
            result = cache.update()
        self.assertEqual(result.data, _SUCCESS_DATA)

    def test_retry_after_used_for_backoff(self):
        cache = _make_cache()
        error = {'error': 'HTTP 429', 'rate_limited': True, 'retry_after': 300}
        with patch('usage_monitor_for_claude.cache.fetch_provider_data', return_value=pfr(error)), \
             patch('usage_monitor_for_claude.cache.time') as mock_time:
            mock_time.time.return_value = 1000.0
            cache.update()
        self.assertEqual(cache._rate_limit_until, 1300.0)

    def test_retry_after_capped_by_max_backoff(self):
        cache = _make_cache()
        error = {'error': 'HTTP 429', 'rate_limited': True, 'retry_after': 86400}
        with patch('usage_monitor_for_claude.cache.fetch_provider_data', return_value=pfr(error)), \
             patch('usage_monitor_for_claude.cache.time') as mock_time, \
             patch('usage_monitor_for_claude.cache.MAX_BACKOFF', 900):
            mock_time.time.return_value = 1000.0
            cache.update()
        self.assertEqual(cache._rate_limit_until, 1900.0)

    def test_exponential_backoff_on_repeated_429(self):
        cache = _make_cache()
        error = {'error': 'HTTP 429', 'rate_limited': True}
        with patch('usage_monitor_for_claude.cache.fetch_provider_data', return_value=pfr(error)), \
             patch('usage_monitor_for_claude.cache.time') as mock_time:
            mock_time.time.return_value = 1000.0
            cache.update()
            first = cache._rate_limit_until
            cache.update(force=True)
            second = cache._rate_limit_until
        self.assertGreater(second, first)

    def test_success_clears_rate_limit(self):
        cache = _make_cache()
        cache._rate_limit_until = 2000.0
        with patch('usage_monitor_for_claude.cache.fetch_provider_data', return_value=pfr(_SUCCESS_DATA)):
            cache.update(force=True)
        self.assertEqual(cache._rate_limit_until, 0)

    def test_non_429_error_does_not_set_rate_limit(self):
        cache = _make_cache()
        with patch('usage_monitor_for_claude.cache.fetch_provider_data', return_value=pfr(_ERROR_DATA)):
            cache.update()
        self.assertEqual(cache._rate_limit_until, 0)


class TestRateLimitRemaining(unittest.TestCase):
    def test_active_rate_limit(self):
        cache = _make_cache()
        cache._rate_limit_until = 1300.0
        with patch('usage_monitor_for_claude.cache.time.time', return_value=1000.0):
            self.assertEqual(cache.rate_limit_remaining, 300.0)

    def test_expired_rate_limit(self):
        cache = _make_cache()
        cache._rate_limit_until = 1000.0
        with patch('usage_monitor_for_claude.cache.time.time', return_value=1001.0):
            self.assertEqual(cache.rate_limit_remaining, 0)

    def test_no_rate_limit(self):
        self.assertEqual(_make_cache().rate_limit_remaining, 0)


class TestSnapshot(unittest.TestCase):
    def test_snapshot_type_and_state(self):
        cache = _make_cache()
        cache._usage = _SUCCESS_DATA
        cache._profile = _PROFILE_A
        snapshot = cache.snapshot
        self.assertIsInstance(snapshot, CacheSnapshot)
        self.assertEqual(snapshot.usage, _SUCCESS_DATA)
        self.assertEqual(snapshot.profile, _PROFILE_A)

    def test_snapshot_is_frozen(self):
        snapshot = _make_cache().snapshot
        with self.assertRaises(Exception):
            snapshot.version = 3


class TestProfileSemantics(unittest.TestCase):
    def _update(self, cache, usage, profile, recovery=False):
        with patch('usage_monitor_for_claude.cache.fetch_provider_data', return_value=pfr(usage, profile, recovery)), \
             patch('usage_monitor_for_claude.cache.POLL_FAST', 0):
            return cache.update()

    def test_dict_profile_stored_with_usage(self):
        cache = _make_cache()
        self._update(cache, _SUCCESS_DATA, _PROFILE_A)
        self.assertEqual(cache.profile, _PROFILE_A)

    def test_none_preserves_cached_profile(self):
        cache = _make_cache()
        self._update(cache, _SUCCESS_DATA, _PROFILE_A)
        self._update(cache, _ERROR_DATA, None)
        self.assertEqual(cache.profile, _PROFILE_A)

    def test_empty_dict_replaces_with_signed_out(self):
        cache = _make_cache()
        self._update(cache, _SUCCESS_DATA, _PROFILE_A)
        self._update(cache, {'error': 'signed out', 'no_auth': True}, {})
        self.assertEqual(cache.profile, {})

    def test_profile_stored_even_on_error_cycle(self):
        cache = _make_cache()
        self._update(cache, _ERROR_DATA, _PROFILE_A)
        self.assertEqual(cache.profile, _PROFILE_A)


class TestEpisodeGuard(unittest.TestCase):
    def _cycle(self, cache, usage, profile, recovery_attempted):
        observed = []

        def fake_fetch(allow_recovery=False):
            observed.append(allow_recovery)
            return pfr(usage, profile, recovery_attempted)

        with patch('usage_monitor_for_claude.cache.fetch_provider_data', side_effect=fake_fetch), \
             patch('usage_monitor_for_claude.cache.POLL_FAST', 0):
            cache.update()
        return observed[0]

    def test_first_failing_cycle_allows_recovery_second_does_not(self):
        cache = _make_cache()
        self.assertTrue(self._cycle(cache, _ERROR_DATA, None, True))
        self.assertFalse(self._cycle(cache, _ERROR_DATA, None, False))
        self.assertFalse(self._cycle(cache, _ERROR_DATA, None, False))

    def test_transient_only_episode_consumes_once(self):
        cache = _make_cache()
        self.assertTrue(self._cycle(cache, {'error': 'transient'}, None, True))
        self.assertFalse(self._cycle(cache, {'error': 'transient'}, None, False))

    def test_success_resets_guard(self):
        cache = _make_cache()
        self._cycle(cache, _ERROR_DATA, None, True)
        self._cycle(cache, _SUCCESS_DATA, _PROFILE_A, False)
        self.assertTrue(self._cycle(cache, _ERROR_DATA, None, True))

    def test_fingerprint_change_resets_guard(self):
        cache = _make_cache()
        self._cycle(cache, _ERROR_DATA, _PROFILE_A, True)
        self._cycle(cache, _ERROR_DATA, _PROFILE_B, False)
        self.assertTrue(self._cycle(cache, _ERROR_DATA, _PROFILE_B, True))


class TestSnapshotErrorProfileAtomicity(unittest.TestCase):
    """Snapshots never pair a newly stored error with a stale profile."""

    def test_error_and_profile_change_together(self):
        cache = _make_cache()
        stop = threading.Event()
        violations = []

        def watcher():
            while not stop.is_set():
                snapshot = cache.snapshot
                if snapshot.last_error and snapshot.last_error.startswith('err-'):
                    index = snapshot.last_error.split('-')[1]
                    email = (snapshot.profile or {}).get('account', {}).get('email', '')
                    if email != f'u{index}@x':
                        violations.append((snapshot.last_error, email))

        thread = threading.Thread(target=watcher, daemon=True)
        thread.start()
        try:
            for index in range(200):
                profile = {
                    'account': {'email': f'u{index}@x', 'uuid': f'chatgpt:u{index}@x'},
                    'organization': {'organization_type': ''},
                }
                with patch('usage_monitor_for_claude.cache.fetch_provider_data',
                           return_value=pfr({'error': f'err-{index}'}, profile)), \
                     patch('usage_monitor_for_claude.cache.POLL_FAST', 0):
                    cache.update()
        finally:
            stop.set()
            thread.join(timeout=5)
        self.assertEqual(violations, [])


class TestProfileOnlyMethods(unittest.TestCase):
    def test_ensure_profile_fetches_once(self):
        cache = _make_cache()
        with patch('usage_monitor_for_claude.cache.adapter_refresh_profile', return_value=_PROFILE_A) as refresh:
            cache.ensure_profile()
            cache.ensure_profile()
        refresh.assert_called_once()
        self.assertEqual(cache.profile, _PROFILE_A)

    def test_ensure_profile_skips_during_backoff(self):
        cache = _make_cache()
        cache._rate_limit_until = 1300.0
        with patch('usage_monitor_for_claude.cache.time.time', return_value=1000.0), \
             patch('usage_monitor_for_claude.cache.adapter_refresh_profile') as refresh:
            cache.ensure_profile()
        refresh.assert_not_called()

    def test_ensure_profile_bypass_fetches_during_backoff(self):
        cache = _make_cache()
        cache._rate_limit_until = 1300.0
        with patch('usage_monitor_for_claude.cache.time.time', return_value=1000.0), \
             patch('usage_monitor_for_claude.cache.adapter_refresh_profile', return_value=_PROFILE_A) as refresh:
            cache.ensure_profile(bypass_rate_limit=True)
        refresh.assert_called_once()

    def test_concurrent_ensure_profile_calls_fetch_once(self):
        cache = _make_cache()
        entered = threading.Event()
        release = threading.Event()

        def fetch():
            entered.set()
            release.wait(timeout=5)
            return _PROFILE_A

        with patch('usage_monitor_for_claude.cache.adapter_refresh_profile', side_effect=fetch) as refresh:
            first = threading.Thread(target=cache.ensure_profile)
            second = threading.Thread(target=cache.ensure_profile)
            first.start()
            entered.wait(timeout=5)
            second.start()
            release.set()
            first.join(timeout=5)
            second.join(timeout=5)
        refresh.assert_called_once()

    def test_refresh_profile_works_inside_usage_cooldown(self):
        cache = _make_cache()
        with patch('usage_monitor_for_claude.cache.fetch_provider_data', return_value=pfr(_SUCCESS_DATA, _PROFILE_A)):
            cache.update()
        with patch('usage_monitor_for_claude.cache.adapter_refresh_profile', return_value=_PROFILE_B):
            cache.refresh_profile()
        self.assertEqual(cache.profile, _PROFILE_B)

    def test_refresh_profile_none_preserves(self):
        cache = _make_cache()
        with patch('usage_monitor_for_claude.cache.adapter_refresh_profile', return_value=_PROFILE_A):
            cache.refresh_profile()
        with patch('usage_monitor_for_claude.cache.adapter_refresh_profile', return_value=None):
            cache.refresh_profile()
        self.assertEqual(cache.profile, _PROFILE_A)

    def test_profile_only_read_cannot_overtake_combined_update_commit(self):
        cache = _make_cache()
        provider_entered = threading.Event()
        release_provider = threading.Event()
        refresh_called = threading.Event()

        def fetch_provider(allow_recovery=False):
            provider_entered.set()
            release_provider.wait(timeout=5)
            return pfr(_SUCCESS_DATA, _PROFILE_A)

        def read_profile():
            refresh_called.set()
            return _PROFILE_B

        with patch('usage_monitor_for_claude.cache.fetch_provider_data', side_effect=fetch_provider), \
             patch('usage_monitor_for_claude.cache.adapter_refresh_profile', side_effect=read_profile):
            update_thread = threading.Thread(target=cache.update)
            refresh_thread = threading.Thread(target=cache.refresh_profile)
            update_thread.start()
            self.assertTrue(provider_entered.wait(timeout=5))
            refresh_thread.start()
            time.sleep(0.02)
            self.assertFalse(refresh_called.is_set())
            release_provider.set()
            update_thread.join(timeout=5)
            refresh_thread.join(timeout=5)

        self.assertFalse(update_thread.is_alive())
        self.assertFalse(refresh_thread.is_alive())
        self.assertEqual(cache.profile, _PROFILE_B)


class TestUpdateResult(unittest.TestCase):
    def test_skipped_result(self):
        self.assertIsNone(UpdateResult(data=None).data)


class TestCodexCliUpdate(unittest.TestCase):
    def test_update_is_exclusive_and_stops_transport_first(self):
        cache = _make_cache()
        expected = CliUpdateResult(True, True, '0.140.0', '0.144.5', '')
        events = []

        with patch('usage_monitor_for_claude.cache.shutdown_transport', side_effect=lambda: events.append('shutdown')), \
             patch('usage_monitor_for_claude.cache.update_cli', side_effect=lambda: events.append('update') or expected):
            result = cache.update_codex_cli()

        self.assertEqual(result, expected)
        self.assertEqual(events, ['shutdown', 'update'])

    def test_provider_update_is_skipped_while_cli_update_holds_lock(self):
        cache = _make_cache()
        entered = threading.Event()
        release = threading.Event()

        def slow_update():
            entered.set()
            release.wait(timeout=5)
            return CliUpdateResult(True, False, '0.144.5', '0.144.5', '')

        with patch('usage_monitor_for_claude.cache.shutdown_transport'), \
             patch('usage_monitor_for_claude.cache.update_cli', side_effect=slow_update):
            thread = threading.Thread(target=cache.update_codex_cli)
            thread.start()
            self.assertTrue(entered.wait(timeout=2))
            self.assertIsNone(cache.update().data)
            release.set()
            thread.join(timeout=5)
        self.assertFalse(thread.is_alive())


class TestNullQuotaFields(unittest.TestCase):
    def test_null_quota_fields_do_not_crash(self):
        data = {'five_hour': None, 'seven_day': None}
        cache = _make_cache()
        with patch('usage_monitor_for_claude.cache.fetch_provider_data', return_value=pfr(data)):
            self.assertEqual(cache.update().data, data)

    def test_mixed_null_and_valid_quota_fields(self):
        data = {'five_hour': None, 'seven_day': {'utilization': 30.0}}
        cache = _make_cache()
        with patch('usage_monitor_for_claude.cache.fetch_provider_data', return_value=pfr(data)):
            self.assertEqual(cache.update().data, data)

    def test_empty_response_treated_as_success(self):
        cache = _make_cache()
        with patch('usage_monitor_for_claude.cache.fetch_provider_data', return_value=pfr({})):
            self.assertEqual(cache.update().data, {})


if __name__ == '__main__':
    unittest.main()
