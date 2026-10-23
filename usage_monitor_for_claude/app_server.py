"""
App-Server Transport
=====================

Owns the single long-lived ``codex app-server`` child process and speaks
JSON-RPC 2.0 semantics over newline-delimited JSON (the ``jsonrpc`` version
header is omitted on the wire, per the official app-server protocol).

Security-critical module: together with ``api.py`` it forms the provider
boundary. It never accesses credential files and never logs payloads,
tokens, or email - only method names, durations, and error codes.
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, TypeVar

if TYPE_CHECKING:
    from .provider_process_linux import ControlPipe

__all__ = ['CHILD_TTL', 'INIT_TIMEOUT', 'RPC_TIMEOUT', 'AppServerTransport', 'CodexCliNotFound', 'RpcError', 'TransportError', 'discover_codex_command']

CHILD_TTL = 600
INIT_TIMEOUT = 30
RPC_TIMEOUT = 10
SHUTDOWN_GRACE = 2.0
SHUTDOWN_TIMEOUT = 5.0
CLEANUP_RETRY_DELAY = 30.0

log = logging.getLogger(__name__)

STDERR_RING_SIZE = 20
IS_WINDOWS = sys.platform == 'win32'
T_ = TypeVar('T_')

if IS_WINDOWS:
    from .provider_process_windows import _kernel32, ctypes


class TransportError(Exception):
    """Transport-level failure: spawn, handshake, timeout, child death, or protocol violation."""


class CodexCliNotFound(TransportError):
    """The codex CLI binary could not be located."""


class RpcError(Exception):
    """A JSON-RPC error response from the app-server."""

    def __init__(self, code: int | None, message: str, data: Any = None) -> None:
        super().__init__(f'{code}: {message}')
        self.code = code
        self.message = message
        self.data = data


def discover_codex_command() -> list[str]:
    """Locate the codex CLI and return the app-server launch command.

    Search PATH first. Windows also checks executable siblings of PowerShell
    shims, the native installer and npm's global directory. Linux checks the
    user's native bin directory and standard system bin directories.

    Returns
    -------
    list[str]
        The full argv, e.g. ``['C:\\...\\codex.exe', 'app-server']``.

    Raises
    ------
    CodexCliNotFound
        If no codex binary exists in any known location.
    """
    found = shutil.which('codex')
    if found:
        path = Path(found)
        if path.suffix.lower() == '.ps1':
            for extension in ('.cmd', '.exe'):
                executable_sibling = path.with_suffix(extension)
                if executable_sibling.is_file():
                    return [str(executable_sibling), 'app-server']
        else:
            return [str(path), 'app-server']

    if not IS_WINDOWS:
        for candidate in (Path.home() / '.local' / 'bin' / 'codex', Path('/usr/local/bin/codex'), Path('/usr/bin/codex')):
            if candidate.is_file():
                return [str(candidate), 'app-server']
        raise CodexCliNotFound('codex CLI not found')

    localappdata = os.environ.get('LOCALAPPDATA')
    if localappdata:
        candidate = Path(localappdata) / 'Programs' / 'OpenAI' / 'Codex' / 'bin' / 'codex.exe'
        if candidate.is_file():
            return [str(candidate), 'app-server']

    appdata = os.environ.get('APPDATA')
    if appdata:
        for name in ('codex.cmd', 'codex.exe'):
            candidate = Path(appdata) / 'npm' / name
            if candidate.is_file():
                return [str(candidate), 'app-server']

    raise CodexCliNotFound('codex CLI not found')


def _assign_kill_on_close_job(process_handle: int) -> int:
    """Create native containment while preserving the transport error contract."""
    from .provider_process_windows import assign_kill_on_close_job
    try:
        return assign_kill_on_close_job(process_handle)
    except OSError as error:
        raise TransportError(str(error)) from error


def _close_job_handle(job: int) -> None:
    from .provider_process_windows import close_job_handle
    try:
        close_job_handle(job)
    except OSError as error:
        raise TransportError(str(error)) from error


def _wait_process_handle(handle: int, timeout: float) -> bool:
    """Confirm native process completion without trusting a cached exit code."""
    from .provider_process_windows import wait_process_handle
    try:
        return wait_process_handle(handle, timeout)
    except OSError as error:
        raise TransportError(str(error)) from error


def _terminate_job(job: int) -> None:
    from .provider_process_windows import terminate_job
    try:
        terminate_job(job)
    except OSError as error:
        raise TransportError(str(error)) from error


def _job_process_ids(job: int) -> list[int]:
    """Read a complete native containment snapshot for exit tracking."""
    from .provider_process_windows import job_process_ids
    try:
        return job_process_ids(job)
    except OSError as error:
        raise TransportError(str(error)) from error


def _open_job_process(job: int, pid: int) -> int | None:
    """Retain a wait handle only for a current member of the child Job."""
    from .provider_process_windows import open_job_process
    try:
        return open_job_process(job, pid)
    except OSError as error:
        raise TransportError(str(error)) from error


def _redact(line: str) -> str:
    """Strip the home directory and token-shaped runs from a diagnostic line."""
    home = str(Path.home())
    redacted = line
    variants = {home, home.replace('\\', '/'), home.replace('\\', '\\\\')}
    for variant in sorted(variants, key=len, reverse=True):
        if variant:
            redacted = re.sub(re.escape(variant), '~', redacted, flags=re.IGNORECASE)
    return re.sub(r'[A-Za-z0-9_\-\.=\/+]{24,}', '***', redacted.rstrip('\n'))


class _Pending:
    __slots__ = ('event', 'response')

    def __init__(self) -> None:
        self.event = threading.Event()
        self.response: dict[str, Any] | None = None


class _OperationHandle:
    """Request interface handed to an operation body and pinned to one generation."""

    def __init__(self, transport: AppServerTransport, generation: int) -> None:
        self._transport = transport
        self._generation = generation
        self._active = True

    def request(self, method: str, params: dict[str, Any]) -> Any:
        if not self._active:
            raise TransportError('provider operation already finished')
        return self._transport._request(self._generation, method, params)

    def _invalidate(self) -> None:
        self._active = False


class AppServerTransport:
    """Own one ``codex app-server`` child and execute atomic provider operations."""

    def __init__(self, command: list[str] | None = None, *, child_ttl: int = CHILD_TTL,
                 init_timeout: float = INIT_TIMEOUT, rpc_timeout: float = RPC_TIMEOUT,
                 codex_home: str | None = None) -> None:
        self._command = command
        self._child_ttl = child_ttl
        self._init_timeout = init_timeout
        self._rpc_timeout = rpc_timeout
        self._codex_home = codex_home

        self._op_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._stdin_lock = threading.Lock()

        self._proc: subprocess.Popen | None = None
        self._job_handle: int | None = None
        self._linux_control: ControlPipe | None = None
        self._generation = 0
        self._dead = True
        self._child_started_at = 0.0
        self._next_id = 0
        self._pending: dict[int | str, _Pending] = {}
        self._auth_revision = 0
        self._stderr_ring: deque[str] = deque(maxlen=STDERR_RING_SIZE)
        self._reader_threads: list[threading.Thread] = []
        self._exit_handles: dict[int, int] = {}
        self._cleanup_retry_at = 0.0

    def run_operation(self, body: Callable[[_OperationHandle], T_]) -> T_:
        """Run one generation-atomic provider operation, retrying once after transport failure."""
        with self._op_lock:
            self._ensure_child()
            for attempt in (0, 1):
                with self._state_lock:
                    generation = self._generation
                operation = _OperationHandle(self, generation)
                try:
                    return body(operation)
                except TransportError:
                    self._kill_child(reason='transport failure', graceful=False)
                    if attempt == 1:
                        raise
                    self._ensure_child()
                finally:
                    operation._invalidate()
            raise TransportError('unreachable')  # pragma: no cover

    def auth_revision(self) -> int:
        with self._state_lock:
            return self._auth_revision

    def force_restart(self) -> None:
        """Terminate the child so the next operation creates a fresh generation."""
        with self._op_lock:
            self._kill_child(reason='requested restart')

    def shutdown(self) -> None:
        with self._op_lock:
            self._kill_child(reason='shutdown')

    def stderr_tail(self) -> list[str]:
        with self._state_lock:
            return list(self._stderr_ring)

    def _ensure_child(self) -> None:
        with self._state_lock:
            alive = self._proc is not None and not self._dead and self._proc.poll() is None
            expired = alive and time.monotonic() - self._child_started_at > self._child_ttl
        if alive and not expired:
            return
        self._kill_child(reason='ttl expired' if expired else 'child unavailable', graceful=alive)
        self._spawn()

    def _spawn(self) -> None:
        command = self._command or discover_codex_command()
        environment = dict(os.environ)
        if self._codex_home:
            environment['CODEX_HOME'] = self._codex_home

        control = None
        try:
            if IS_WINDOWS:
                process = subprocess.Popen(
                    command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, encoding='utf-8', errors='replace', bufsize=0, env=environment,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            else:
                from .provider_process_linux import spawn_supervised
                process, control = spawn_supervised(command, environment)
        except OSError as error:
            code = getattr(error, 'winerror', None) or getattr(error, 'errno', None) or '?'
            raise TransportError(f'spawn failed (OS error {code})') from error

        with self._state_lock:
            self._proc = process
            self._linux_control = control
            self._generation += 1
            self._child_started_at = time.monotonic()
            generation = self._generation

        job = None
        if IS_WINDOWS:
            try:
                job = _assign_kill_on_close_job(int(process._handle))  # type: ignore[attr-defined]  # Native Job requires Popen's Win32 handle.
            except TransportError:
                self._kill_child(reason='job assignment failed', graceful=False)
                raise

        with self._state_lock:
            self._job_handle = job
            self._dead = False
        log.info('child started (generation=%s, pid=%s)', generation, process.pid)
        from . import __version__
        try:
            for target in (self._reader, self._drain_stderr):
                reader = threading.Thread(target=target, args=(process, generation), daemon=True)
                reader.start()
                self._reader_threads.append(reader)
            initialize_result = self._request(
                generation,
                'initialize',
                {'clientInfo': {'name': 'usage-monitor-for-codex', 'title': 'Usage Monitor for Codex', 'version': __version__}},
                timeout=self._init_timeout,
            )
            log.info('initialize -> OK (%s)', type(initialize_result).__name__)
            self._write_line(json.dumps({'method': 'initialized', 'params': {}}), generation, process)
        except (TransportError, RpcError, RuntimeError, OSError) as exc:
            self._kill_child(reason='handshake failed', graceful=False)
            raise TransportError('child initialization failed') from exc

    def _close_stdin(self, process: subprocess.Popen, timeout: float) -> bool:
        """Attempt EOF without waiting indefinitely for an outstanding pipe writer."""
        if not self._stdin_lock.acquire(timeout=timeout):
            return False
        try:
            if process.stdin is not None:
                try:
                    process.stdin.close()
                except (OSError, ValueError):
                    pass
            return True
        finally:
            self._stdin_lock.release()

    def _capture_exit_handles(self, process: subprocess.Popen, job: int | None) -> list[int]:
        """Retain descendant handles before requesting exit and during draining."""
        if job is None:
            return []
        pids = _job_process_ids(job)
        for pid in pids:
            if pid == process.pid or pid in self._exit_handles:
                continue
            handle = _open_job_process(job, pid)
            if handle is not None:
                self._exit_handles[pid] = handle
        return pids

    def _wait_for_exit(self, process: subprocess.Popen, job: int | None, timeout: float) -> bool:
        """Require signaled process handles and an empty Job within one deadline."""
        deadline = time.monotonic() + timeout
        while True:
            pids = self._capture_exit_handles(process, job)
            handles = [int(process._handle), *self._exit_handles.values()]  # type: ignore[attr-defined]  # Bypass Popen's cached returncode
            waiting = [handle for handle in handles if not _wait_process_handle(handle, 0)]
            if not waiting and not pids:
                return True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            interval = min(0.05, remaining)
            if waiting:
                _wait_process_handle(waiting[0], interval)
            else:
                time.sleep(interval)

    def _kill_child(self, *, reason: str = 'cleanup', graceful: bool = True) -> None:
        """Retire one generation, retaining ownership if exit cannot be confirmed.

        The caller holds the operation lock. Reader threads only mark failure;
        they never close Job handles or terminate processes independently.
        """
        with self._state_lock:
            process = self._proc
            job = self._job_handle
            control = self._linux_control
            self._dead = True
            pending_requests = list(self._pending.values())
            self._pending.clear()
        for pending in pending_requests:
            pending.response = None
            pending.event.set()

        if process is None:
            return
        if time.monotonic() < self._cleanup_retry_at:
            raise TransportError('previous child exit is unconfirmed; cleanup retry deferred')

        started = time.monotonic()
        method = 'graceful' if graceful else 'forced'
        log.info('child stopping (generation=%s, pid=%s, reason=%s)', self._generation, process.pid, reason)
        try:
            if control is not None:
                from .provider_process_linux import STARTUP_FAILURE_EXIT
                # Deliver liveness EOF before attempting any potentially busy pipe lock.
                control.close()
                self._close_stdin(process, 0)
                return_code = process.wait(timeout=SHUTDOWN_TIMEOUT)
                if return_code not in (0, STARTUP_FAILURE_EXIT):
                    raise TransportError('supervisor exit cannot confirm descendant cleanup')
            else:
                self._capture_exit_handles(process, job)
                # Unbuffered stdin has no pending user-space data to flush on close.
                eof_sent = self._close_stdin(process, SHUTDOWN_GRACE if graceful else 0)
                exited = self._wait_for_exit(process, job, SHUTDOWN_GRACE if graceful and eof_sent else 0)
                if not exited:
                    method = 'forced'
                    log.info('child termination requested (generation=%s, pid=%s)', self._generation, process.pid)
                    if job is not None:
                        _terminate_job(job)
                    else:
                        process.kill()
                    if not self._wait_for_exit(process, job, SHUTDOWN_TIMEOUT):
                        raise TransportError('child process handles did not signal before shutdown deadline')

            # The platform wait above confirms completion before releasing ownership.
            process.wait(timeout=0)
            for reader in self._reader_threads:
                reader.join(timeout=1)
            if any(reader.is_alive() for reader in self._reader_threads):
                raise TransportError('child pipe readers have not finished')
            if not self._close_stdin(process, 0):
                raise TransportError('child stdin writer has not finished')
            for stream in (process.stdout, process.stderr):
                if stream is not None:
                    stream.close()
            if job is not None:
                _close_job_handle(job)
        except (TransportError, OSError, subprocess.TimeoutExpired) as error:
            self._cleanup_retry_at = time.monotonic() + CLEANUP_RETRY_DELAY
            log.warning('child exit unconfirmed; replacement deferred (generation=%s, pid=%s, failure=%s)',
                        self._generation, process.pid, type(error).__name__)
            raise TransportError('child cleanup incomplete; replacement deferred') from error

        for handle in self._exit_handles.values():
            _kernel32.CloseHandle(handle)
        self._exit_handles.clear()
        self._reader_threads.clear()
        self._cleanup_retry_at = 0.0
        with self._state_lock:
            self._proc = None
            self._job_handle = None
            self._linux_control = None
        log.info('child exit confirmed (generation=%s, pid=%s, method=%s, elapsed=%.2fs)',
                 self._generation, process.pid, method, time.monotonic() - started)

    def _write_line(self, line: str, generation: int, process: subprocess.Popen) -> None:
        with self._stdin_lock:
            with self._state_lock:
                if generation != self._generation or process is not self._proc or self._dead:
                    raise TransportError('child generation changed')
                stdin = process.stdin
            if stdin is None:
                raise TransportError('child stdin unavailable')
            try:
                payload = (line + '\n').encode('utf-8')
                offset = 0
                while offset < len(payload):
                    with self._state_lock:
                        if generation != self._generation or process is not self._proc or self._dead:
                            raise TransportError('child generation changed')
                    written = stdin.buffer.write(payload[offset:])
                    if written is None or written <= 0:
                        raise TransportError('child stdin write made no progress')
                    offset += written
                stdin.flush()
            except (OSError, ValueError) as exc:
                raise TransportError(f'write failed: {exc}') from exc

    def _request(self, generation: int, method: str, params: dict[str, Any], timeout: float | None = None) -> Any:
        pending = _Pending()
        with self._state_lock:
            if generation != self._generation or self._dead or self._proc is None:
                raise TransportError('child generation changed')
            process = self._proc
            self._next_id += 1
            request_id = self._next_id
            self._pending[request_id] = pending

        started = time.monotonic()
        try:
            self._write_line(json.dumps({'id': request_id, 'method': method, 'params': params}), generation, process)
        except TransportError:
            with self._state_lock:
                self._pending.pop(request_id, None)
            raise
        if not pending.event.wait(timeout if timeout is not None else self._rpc_timeout):
            with self._state_lock:
                self._pending.pop(request_id, None)
            log.warning('%s -> timeout after %.1fs', method, time.monotonic() - started)
            raise TransportError(f'{method} timed out')

        response = pending.response
        if response is None:
            raise TransportError('child died during request or sent a protocol error')
        if 'error' in response:
            error = response['error']
            assert isinstance(error, dict)
            log.warning('%s -> rpc error %s', method, error.get('code'))
            raise RpcError(error.get('code'), error.get('message', ''), error.get('data'))
        log.info('%s -> OK (%.2fs)', method, time.monotonic() - started)
        return response['result']

    def _reader(self, process: subprocess.Popen, generation: int) -> None:
        assert process.stdout is not None
        for line in process.stdout:
            if not line.strip():
                continue
            try:
                message = json.loads(line)
                if not isinstance(message, dict):
                    raise TransportError('protocol message is not an object')
                self._dispatch_message(process, generation, message)
            except (ValueError, TransportError):
                log.warning('malformed protocol message from child')
                self._fail_generation(process, generation)
                return
        self._fail_generation(process, generation)

    def _dispatch_message(self, process: subprocess.Popen, generation: int, message: dict[str, Any]) -> None:
        with self._state_lock:
            if generation != self._generation or process is not self._proc or self._dead:
                return

        has_id = 'id' in message
        has_result = 'result' in message
        has_error = 'error' in message
        if has_result or has_error:
            if not has_id or has_result == has_error:
                raise TransportError('malformed response envelope')
            response_id = message['id']
            if isinstance(response_id, bool) or not isinstance(response_id, (int, str)):
                raise TransportError('malformed response id')
            if has_error:
                error = message['error']
                if not isinstance(error, dict) or not isinstance(error.get('message', ''), str):
                    raise TransportError('malformed error envelope')
                if error.get('code') is not None and not isinstance(error.get('code'), int):
                    raise TransportError('malformed error code')
            with self._state_lock:
                if generation != self._generation or process is not self._proc or self._dead:
                    return
                pending = self._pending.pop(response_id, None)
            if pending is not None:
                pending.response = message
                pending.event.set()
            return

        if has_id:
            method = message.get('method')
            if not isinstance(method, str):
                raise TransportError('malformed server request')
            response = {'id': message['id'], 'error': {'code': -32601, 'message': 'method not supported'}}
            self._write_line(json.dumps(response), generation, process)
            return

        method = message.get('method')
        if not isinstance(method, str):
            raise TransportError('malformed notification')
        if method == 'account/updated':
            with self._state_lock:
                if generation == self._generation and process is self._proc and not self._dead:
                    self._auth_revision += 1

    def _fail_generation(self, process: subprocess.Popen, generation: int) -> None:
        with self._state_lock:
            if generation != self._generation or process is not self._proc or self._dead:
                return
            self._dead = True
            pending_requests = list(self._pending.values())
            self._pending.clear()
        for pending in pending_requests:
            pending.response = None
            pending.event.set()

    def _drain_stderr(self, process: subprocess.Popen, generation: int) -> None:
        assert process.stderr is not None
        for line in process.stderr:
            with self._state_lock:
                if generation == self._generation and process is self._proc and not self._dead:
                    self._stderr_ring.append(_redact(line))
