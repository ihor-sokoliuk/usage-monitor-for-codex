"""Linux subreaper supervising only the Codex provider's descendant tree.

The monitor owns a liveness pipe writer. Its EOF requests cleanup without
sharing that descriptor with the provider. Provider stdio is inherited directly;
this helper never writes control records to the JSONL stdout stream.
"""
from __future__ import annotations

import ctypes
import os
import select
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

__all__ = ['main']

_EOF_GRACE = 0.35
_TERM_GRACE = 0.5
_KILL_GRACE = 2.0
_POLL_INTERVAL = 0.025
_stop_requested = False


@dataclass(frozen=True)
class ProcessIdentity:
    """A Linux process identity and its current ancestry."""

    pid: int
    start_time: int
    parent_pid: int
    state: str


def _request_stop(_signal_number: int, _frame: object) -> None:
    global _stop_requested
    _stop_requested = True


def _read_identity(pid: int) -> ProcessIdentity | None:
    """Read /proc identity without trusting a stale numeric PID."""
    try:
        # The comm field may contain spaces and parentheses; its final ')' ends it.
        fields = (Path('/proc') / str(pid) / 'stat').read_text(encoding='utf-8', errors='replace').rsplit(')', 1)[1].split()
        return ProcessIdentity(pid, int(fields[19]), int(fields[1]), fields[0])
    except (OSError, ValueError, IndexError):
        return None


def _owned_descendants(anchor_pid: int) -> dict[int, ProcessIdentity]:
    """Snapshot descendants, including children adopted by this subreaper."""
    identities: dict[int, ProcessIdentity] = {}
    for entry in Path('/proc').iterdir():
        if not entry.name.isdecimal():
            continue
        identity = _read_identity(int(entry.name))
        if identity is not None:
            identities[identity.pid] = identity
    owned = {}
    for pid, identity in identities.items():
        ancestor = identity.parent_pid
        visited = {pid}
        while ancestor not in visited:
            if ancestor == anchor_pid:
                owned[pid] = identity
                break
            visited.add(ancestor)
            parent = identities.get(ancestor)
            if parent is None:
                break
            ancestor = parent.parent_pid
    return owned


def _signal_owned(identities: dict[int, ProcessIdentity], signal_number: int, anchor_pid: int) -> None:
    """Signal stable pidfds only after rechecking identity and live ancestry."""
    for pid, identity in identities.items():
        if identity.state == 'Z':
            continue
        try:
            descriptor = os.pidfd_open(pid)
        except ProcessLookupError:
            continue
        try:
            current = _owned_descendants(anchor_pid).get(pid)
            if current is not None and current.start_time == identity.start_time:
                signal.pidfd_send_signal(descriptor, signal_number)
        except ProcessLookupError:
            pass
        finally:
            os.close(descriptor)


def _reap_exited() -> None:
    """Reap exited direct and adopted children without blocking."""
    while True:
        try:
            pid, _status = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return
        if pid == 0:
            return


def _cleanup_phase(anchor_pid: int, duration: float, signal_number: int | None = None) -> bool:
    """Recheck ownership until all descendants are gone or this phase expires."""
    deadline = time.monotonic() + duration
    while True:
        _reap_exited()
        identities = _owned_descendants(anchor_pid)
        if not identities:
            return True
        if signal_number is not None:
            _signal_owned(identities, signal_number, anchor_pid)
        if time.monotonic() >= deadline:
            return False
        time.sleep(_POLL_INTERVAL)


def _prepare_supervisor() -> None:
    """Install handlers and prove required kernel support before any child spawn."""
    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)
    signal.signal(signal.SIGHUP, _request_stop)
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
    libc.prctl.restype = ctypes.c_int
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
        raise OSError(ctypes.get_errno(), 'subreaper unavailable')
    descriptor = os.pidfd_open(os.getpid())
    try:
        signal.pidfd_send_signal(descriptor, 0)
    finally:
        os.close(descriptor)
    if _read_identity(os.getpid()) is None:
        raise OSError('process identities unavailable')


def main(arguments: list[str] | None = None) -> int:
    """Supervise one fixed argv until child exit, parent EOF or a caught signal.

    Parameters
    ----------
    arguments : list[str] or None
        Inherited liveness-pipe descriptor followed by the provider argv.

    Returns
    -------
    int
        Zero after complete descendant cleanup, or one for a startup failure.
    """
    global _stop_requested
    _stop_requested = False
    arguments = sys.argv[1:] if arguments is None else arguments
    try:
        control_descriptor = int(arguments[0])
        if len(arguments) < 2:
            raise ValueError('missing command')
        _prepare_supervisor()
    except (OSError, ValueError, IndexError, AttributeError):
        print('codex supervisor: unavailable', file=sys.stderr, flush=True)
        return 1

    if _stop_requested:
        return 0
    try:
        child = subprocess.Popen(arguments[1:], close_fds=True)
    except OSError:
        print('codex supervisor: spawn failed', file=sys.stderr, flush=True)
        return 1

    # Only descendants retain the JSONL pipes, so their EOF reaches the monitor.
    os.close(0)
    os.close(1)
    os.close(2)
    try:
        while not _stop_requested and child.poll() is None:
            readable, _, _ = select.select([control_descriptor], [], [], _POLL_INTERVAL)
            if readable and not os.read(control_descriptor, 1):
                break
    finally:
        os.close(control_descriptor)
        anchor_pid = os.getpid()
        cleaned = _cleanup_phase(anchor_pid, _EOF_GRACE)
        if not cleaned:
            cleaned = _cleanup_phase(anchor_pid, _TERM_GRACE, signal.SIGTERM)
        if not cleaned:
            cleaned = _cleanup_phase(anchor_pid, _KILL_GRACE, signal.SIGKILL)
        # An uninterruptible descendant must keep its identity anchor alive;
        # the monitor's bounded wait then refuses restart/update safely.
        while not cleaned:
            cleaned = _cleanup_phase(anchor_pid, 1.0, signal.SIGKILL)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
