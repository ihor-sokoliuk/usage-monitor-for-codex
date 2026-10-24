"""Exercise orderly helper shutdown and refusal to replace unconfirmed exits."""
from __future__ import annotations

import ctypes
import json
import signal
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import usage_monitor_for_claude.api as api_mod
import usage_monitor_for_claude.app_server as app_server_mod
from tests.test_app_server import fake_command, simple_body
from usage_monitor_for_claude.app_server import AppServerTransport, TransportError
from usage_monitor_for_claude.cache import UsageCache


class TestOrderlyShutdown(unittest.TestCase):
    """Use real Windows children without launching Codex or accessing credentials."""

    def test_shutdown_allows_child_to_observe_eof(self):
        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / 'messages.jsonl'
            transport = AppServerTransport(command=fake_command(log=str(log_path)))
            self.addCleanup(transport.shutdown)
            transport.run_operation(simple_body)
            process = transport._proc
            transport.shutdown()
            events = [json.loads(line) for line in log_path.read_text().splitlines()]
            self.assertIn({'event': 'stdin-eof'}, events)
            self.assertEqual(process.returncode, 0)
            self.assertIsNone(transport._proc)
            self.assertIsNone(transport._job_handle)

    def test_ttl_replacement_follows_orderly_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / 'messages.jsonl'
            transport = AppServerTransport(command=fake_command(log=str(log_path)), child_ttl=0)
            self.addCleanup(transport.shutdown)
            transport.run_operation(simple_body)
            old_process = transport._proc
            transport.run_operation(simple_body)
            events = [json.loads(line) for line in log_path.read_text().splitlines()]
            self.assertIn({'event': 'stdin-eof'}, events)
            eof_index = events.index({'event': 'stdin-eof'})
            initialize_indexes = [i for i, event in enumerate(events) if event.get('method') == 'initialize']
            self.assertLess(eof_index, initialize_indexes[1])
            self.assertEqual(old_process.returncode, 0)
            self.assertNotEqual(transport._proc.pid, old_process.pid)

    @unittest.skipUnless(sys.platform == 'win32', 'direct Windows child exit code')
    def test_uncooperative_child_uses_bounded_forced_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / 'messages.jsonl'
            transport = AppServerTransport(command=fake_command('ignore-eof', log=str(log_path)))
            self.addCleanup(transport.shutdown)
            transport.run_operation(simple_body)
            process = transport._proc
            started = time.monotonic()
            with patch.object(app_server_mod, 'SHUTDOWN_GRACE', 0.1, create=True):
                transport.shutdown()
            self.assertLess(time.monotonic() - started, 5)
            events = [json.loads(line) for line in log_path.read_text().splitlines()]
            self.assertIn({'event': 'stdin-eof'}, events)
            self.assertIsNotNone(process.poll())
            self.assertNotEqual(process.returncode, 0)

    @unittest.skipUnless(sys.platform == 'win32', 'Windows descendant wait handles')
    def test_descendant_is_gone_before_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / 'messages.jsonl'
            transport = AppServerTransport(command=fake_command('with-descendant', log=str(log_path)), child_ttl=0)
            self.addCleanup(transport.shutdown)
            transport.run_operation(simple_body)
            old_process = transport._proc
            events = [json.loads(line) for line in log_path.read_text().splitlines()]
            descendant_pid = next(event['descendant_pid'] for event in events if 'descendant_pid' in event)
            handle = app_server_mod._kernel32.OpenProcess(0x00100000, False, descendant_pid)
            self.assertTrue(handle)
            try:
                with patch.object(app_server_mod, 'SHUTDOWN_GRACE', 0.1, create=True):
                    transport.run_operation(simple_body)
                self.assertEqual(app_server_mod._kernel32.WaitForSingleObject(handle, 0), 0)
                self.assertEqual(old_process.returncode, 0)
            finally:
                app_server_mod._kernel32.CloseHandle(handle)

    def test_blocked_server_reply_cannot_prevent_forced_shutdown(self):
        transport = AppServerTransport(command=fake_command('blocked-reply'))
        transport.run_operation(simple_body)
        deadline = time.monotonic() + 2
        while not transport._stdin_lock.locked() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(transport._stdin_lock.locked())
        errors = []

        def shutdown():
            try:
                transport.shutdown()
            except Exception as error:
                errors.append(error)

        with patch.object(app_server_mod, 'SHUTDOWN_GRACE', 0.1):
            worker = threading.Thread(target=shutdown, daemon=True)
            worker.start()
            try:
                worker.join(timeout=2)
                self.assertFalse(worker.is_alive(), 'blocked stdin writer prevented forced termination')
                self.assertEqual(errors, [])
                self.assertIsNone(transport._proc)
            finally:
                if worker.is_alive():
                    if app_server_mod.IS_WINDOWS:
                        app_server_mod._terminate_job(transport._job_handle)
                    else:
                        transport._linux_control.close()
                    worker.join(timeout=5)
                transport.shutdown()

    def test_reader_start_failure_reaps_child_and_allows_retry(self):
        for failed_start in (1, 2):
            with self.subTest(failed_start=failed_start):
                transport = AppServerTransport(command=fake_command())
                self.addCleanup(transport.shutdown)
                start = threading.Thread.start
                calls = 0

                def start_reader(reader):
                    nonlocal calls
                    calls += 1
                    if calls == failed_start:
                        raise RuntimeError('synthetic thread startup failure')
                    start(reader)

                with patch.object(threading.Thread, 'start', start_reader):
                    with self.assertRaises(TransportError):
                        transport.run_operation(simple_body)
                self.assertIsNone(transport._proc)
                self.assertIsNone(transport._job_handle)
                self.assertIn('rateLimits', transport.run_operation(simple_body))


@unittest.skipUnless(sys.platform == 'win32', 'Windows native exit verification')
class TestUnconfirmedExit(unittest.TestCase):
    """Inject OS wait failures that cannot be safely reproduced with live Codex."""

    def setUp(self):
        self.transport = AppServerTransport(command=['synthetic-child'])
        self.process = MagicMock()
        self.process.pid = 1234
        self.process._handle = 123
        self.process.poll.return_value = 0
        self.process.returncode = 0
        self.transport._proc = self.process
        self.transport._job_handle = 456
        self.transport._dead = True
        self.start_patch('_close_job_handle')
        self.start_patch('_job_process_ids', return_value=[], create=True)
        self.start_patch('_terminate_job', create=True)
        self.start_patch('_wait_process_handle', return_value=False, create=True)
        for name in ('SHUTDOWN_GRACE', 'SHUTDOWN_TIMEOUT'):
            patcher = patch.object(app_server_mod, name, 0.01, create=True)
            patcher.start()
            self.addCleanup(patcher.stop)

    def start_patch(self, name, **kwargs):
        patcher = patch.object(app_server_mod, name, **kwargs)
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result

    def test_cached_exit_code_cannot_authorize_replacement(self):
        with patch.object(self.transport, '_spawn') as spawn:
            with self.assertRaises(TransportError):
                self.transport.run_operation(lambda operation: None)
        spawn.assert_not_called()
        self.assertIs(self.transport._proc, self.process)
        self.assertEqual(self.transport._job_handle, 456)

    def test_retry_retains_old_child_until_native_wait_succeeds(self):
        with self.assertRaises(TransportError):
            self.transport.shutdown()
        with patch.object(app_server_mod, '_wait_process_handle', return_value=True), \
             patch.object(app_server_mod.time, 'monotonic', return_value=time.monotonic() + 60):
            self.transport.shutdown()
        self.assertIsNone(self.transport._proc)
        self.assertIsNone(self.transport._job_handle)

    def test_cleanup_failure_defers_repeated_attempts(self):
        with patch.object(self.transport, '_spawn') as spawn, \
             patch.object(app_server_mod, '_terminate_job') as terminate:
            for _ in range(2):
                with self.assertRaises(TransportError):
                    self.transport.run_operation(lambda operation: None)
        self.assertEqual(terminate.call_count, 1)
        spawn.assert_not_called()
        self.assertIs(self.transport._proc, self.process)

    def test_native_wait_error_retains_ownership(self):
        with patch.object(app_server_mod, '_wait_process_handle', side_effect=TransportError('synthetic wait failure')):
            with self.assertRaises(TransportError):
                self.transport.shutdown()
        self.assertIs(self.transport._proc, self.process)
        self.assertEqual(self.transport._job_handle, 456)

    def test_job_query_error_prevents_replacement(self):
        with patch.object(app_server_mod, '_job_process_ids', side_effect=TransportError('synthetic query failure')), \
             patch.object(self.transport, '_spawn') as spawn:
            with self.assertRaises(TransportError):
                self.transport.run_operation(lambda operation: None)
        spawn.assert_not_called()
        self.assertIs(self.transport._proc, self.process)

    def test_zero_job_count_does_not_release_unsignaled_descendant(self):
        self.transport._exit_handles = {9000: 900}
        with patch.object(app_server_mod, '_wait_process_handle', side_effect=lambda handle, timeout: handle != 900):
            with self.assertRaises(TransportError):
                self.transport.shutdown()
        self.assertEqual(self.transport._exit_handles, {9000: 900})
        self.assertIs(self.transport._proc, self.process)

    def test_forced_termination_error_retains_job_for_later_cleanup(self):
        with patch.object(app_server_mod, '_terminate_job', side_effect=TransportError('synthetic termination failure')):
            with self.assertRaises(TransportError):
                self.transport.shutdown()
        self.assertIs(self.transport._proc, self.process)
        self.assertEqual(self.transport._job_handle, 456)

    def test_reader_reports_failure_without_terminating_process(self):
        self.transport._dead = False
        pending = app_server_mod._Pending()
        self.transport._pending[1] = pending
        self.transport._fail_generation(self.process, self.transport._generation)
        self.assertTrue(pending.event.is_set())
        self.assertTrue(self.transport._dead)
        self.assertEqual(self.transport._job_handle, 456)
        self.process.kill.assert_not_called()


class TestCleanupFailureCallers(unittest.TestCase):
    def test_cli_updater_is_skipped_when_exit_is_unconfirmed(self):
        with patch('usage_monitor_for_claude.cache.shutdown_transport', side_effect=TransportError('synthetic failure')), \
             patch('usage_monitor_for_claude.cache.update_cli') as updater:
            result = UsageCache().update_codex_cli()
        self.assertFalse(result.success)
        self.assertFalse(result.updated)
        updater.assert_not_called()

    def test_scheduled_restart_failure_does_not_abort_polling(self):
        transport = MagicMock()
        transport.force_restart.side_effect = TransportError('synthetic failure')
        with patch.object(api_mod, '_transport', transport):
            api_mod.restart_child()
        transport.force_restart.assert_called_once()


@unittest.skipUnless(sys.platform == 'win32', 'Windows Job primitives')
class TestWindowsExitPrimitives(unittest.TestCase):
    """Check Windows failure and variable-length buffer handling at the OS boundary."""

    def test_native_wait_distinguishes_timeout_from_failure(self):
        with patch.object(app_server_mod._kernel32, 'WaitForSingleObject', return_value=258):
            self.assertFalse(app_server_mod._wait_process_handle(0x123456789, 0))
        with patch.object(app_server_mod._kernel32, 'WaitForSingleObject', return_value=0xFFFFFFFF):
            with self.assertRaises(TransportError):
                app_server_mod._wait_process_handle(0x123456789, 0)

    def test_job_snapshot_grows_to_include_all_members(self):
        def query(job, info_class, buffer, size, returned_size):
            header = (ctypes.wintypes.DWORD * 2).from_buffer(buffer)
            header[0] = 20
            if size < 8 + 20 * ctypes.sizeof(ctypes.c_size_t):
                header[1] = 0
                ctypes.set_last_error(234)
                return False
            header[1] = 20
            members = (ctypes.c_size_t * 20).from_buffer(buffer, 8)
            for index in range(20):
                members[index] = 100 + index
            return True

        with patch.object(app_server_mod._kernel32, 'QueryInformationJobObject', side_effect=query):
            self.assertEqual(app_server_mod._job_process_ids(456), list(range(100, 120)))

    def test_job_snapshot_rejects_oversized_or_inconsistent_results(self):
        for assigned, returned in ((5000, 0), (0, 1)):
            with self.subTest(assigned=assigned, returned=returned):
                def query(job, info_class, buffer, size, returned_size):
                    header = (ctypes.wintypes.DWORD * 2).from_buffer(buffer)
                    header[0], header[1] = assigned, returned
                    return True

                with patch.object(app_server_mod._kernel32, 'QueryInformationJobObject', side_effect=query):
                    with self.assertRaises(TransportError):
                        app_server_mod._job_process_ids(456)

    def test_job_snapshot_reports_native_error(self):
        with patch.object(app_server_mod._kernel32, 'QueryInformationJobObject', return_value=False), \
             patch.object(app_server_mod.ctypes, 'get_last_error', return_value=5):
            with self.assertRaises(TransportError):
                app_server_mod._job_process_ids(456)

    def test_inaccessible_member_is_not_treated_as_exited(self):
        with patch.object(app_server_mod._kernel32, 'OpenProcess', return_value=None), \
             patch.object(app_server_mod.ctypes, 'get_last_error', return_value=5):
            with self.assertRaises(TransportError):
                app_server_mod._open_job_process(456, 100)

    def test_vanished_member_is_tolerated(self):
        with patch.object(app_server_mod._kernel32, 'OpenProcess', return_value=None), \
             patch.object(app_server_mod.ctypes, 'get_last_error', return_value=87):
            self.assertIsNone(app_server_mod._open_job_process(456, 100))

    def test_reused_pid_outside_job_is_not_retained(self):
        with patch.object(app_server_mod._kernel32, 'OpenProcess', return_value=0x123456789), \
             patch.object(app_server_mod._kernel32, 'IsProcessInJob', return_value=True), \
             patch.object(app_server_mod._kernel32, 'CloseHandle') as close:
            self.assertIsNone(app_server_mod._open_job_process(456, 100))
        close.assert_called_once_with(0x123456789)


@unittest.skipUnless(sys.platform == 'linux', 'Linux supervisor exit verification')
class TestLinuxSupervisorExit(unittest.TestCase):
    def transport(self, returncode):
        transport = AppServerTransport(command=['synthetic-provider'])
        process = MagicMock()
        process.pid = 1234
        process.returncode = returncode
        process.poll.return_value = returncode
        process.wait.return_value = returncode
        transport._proc = process
        transport._linux_control = MagicMock()
        transport._dead = True
        return transport, process

    def test_abnormal_supervisor_exit_never_authorizes_replacement(self):
        for returncode in (-signal.SIGKILL, 1):
            with self.subTest(returncode=returncode):
                transport, process = self.transport(returncode)
                with patch.object(transport, '_spawn') as spawn:
                    with self.assertRaises(TransportError):
                        transport.run_operation(lambda operation: None)
                self.assertIs(transport._proc, process)
                spawn.assert_not_called()

    def test_distinct_pre_spawn_failure_releases_owned_resources(self):
        transport, _process = self.transport(78)
        transport.shutdown()
        self.assertIsNone(transport._proc)
        self.assertIsNone(transport._linux_control)

    def test_capability_failure_uses_distinct_pre_spawn_code(self):
        from usage_monitor_for_claude import _linux_supervisor as supervisor
        with patch.object(supervisor, '_prepare_supervisor', side_effect=OSError()), \
             patch.object(supervisor.subprocess, 'Popen') as spawn, \
             patch.object(supervisor.sys, 'stderr'):
            self.assertEqual(supervisor.main(['17', '/synthetic-provider']), 78)
        spawn.assert_not_called()


class TestCompletePipeWrites(unittest.TestCase):
    def transport(self):
        transport = AppServerTransport(command=['synthetic-provider'])
        process = MagicMock()
        transport._proc = process
        transport._generation = 1
        transport._dead = False
        return transport, process

    def test_partial_utf8_writes_complete_one_jsonl_line(self):
        transport, process = self.transport()
        process.stdin.buffer.write.side_effect = [1, 2]
        transport._write_line('\u03c0', 1, process)
        self.assertEqual(
            [call.args[0] for call in process.stdin.buffer.write.call_args_list],
            [b'\xcf\x80\n', b'\x80\n'],
        )
        process.stdin.flush.assert_called_once()

    def test_zero_progress_is_a_transport_failure(self):
        transport, process = self.transport()
        process.stdin.buffer.write.return_value = 0
        with self.assertRaises(TransportError):
            transport._write_line('synthetic', 1, process)


if __name__ == '__main__':
    unittest.main()
