"""Real Linux supervisor, process ownership and parent-death regression tests."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import usage_monitor_for_claude.app_server as app_server_mod
from usage_monitor_for_claude.app_server import AppServerTransport, TransportError

CHILD = Path(__file__).with_name('linux_lifecycle_child.py')
PARENT = Path(__file__).with_name('linux_monitor_parent.py')


@unittest.skipUnless(sys.platform == 'linux', 'requires Linux pidfds and /proc')
class TestLinuxLifecycle(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.state = Path(self.temporary.name) / 'events.jsonl'

    def events(self):
        try:
            return [json.loads(line) for line in self.state.read_text().splitlines() if line]
        except FileNotFoundError:
            return []

    def wait_for(self, predicate, timeout=6):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.025)
        self.fail('synthetic lifecycle condition timed out')

    def transport(self, mode='normal', **kwargs):
        transport = AppServerTransport(
            command=[sys.executable, str(CHILD), '--state', str(self.state), '--mode', mode],
            init_timeout=2, rpc_timeout=2, **kwargs,
        )
        self.addCleanup(transport.shutdown)
        return transport

    def assert_children_reaped(self):
        pids = [entry['pid'] for entry in self.events() if entry['event'] in ('child', 'descendant')]
        self.assertTrue(pids)
        self.wait_for(lambda: all(not Path(f'/proc/{pid}').exists() for pid in pids))

    def test_graceful_eof_and_idempotent_shutdown(self):
        transport = self.transport()
        self.assertEqual(transport.run_operation(lambda operation: operation.request('account/read', {})), {'ok': True})
        process = transport._proc
        transport.shutdown()
        transport.shutdown()
        self.assertIsNotNone(process.poll())
        self.assertIn('eof', [entry['event'] for entry in self.events()])
        self.assert_children_reaped()

    def test_stubborn_descendant_and_unrelated_sentinel(self):
        sentinel = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
        self.addCleanup(sentinel.wait)
        self.addCleanup(sentinel.kill)
        transport = self.transport('tree')
        transport.run_operation(lambda operation: None)
        self.wait_for(lambda: any(entry['event'] == 'descendant' for entry in self.events()))
        transport.shutdown()
        self.assertIsNone(sentinel.poll())
        self.assert_children_reaped()

    def test_detached_descendant_is_owned_after_setsid(self):
        transport = self.transport('detached')
        transport.run_operation(lambda operation: None)
        self.wait_for(lambda: any(entry['event'] == 'descendant' for entry in self.events()))
        transport.shutdown()
        self.assert_children_reaped()

    def test_supervisor_sigterm_cleans_detached_descendant(self):
        transport = self.transport('detached')
        transport.run_operation(lambda operation: None)
        self.wait_for(lambda: any(entry['event'] == 'descendant' for entry in self.events()))
        os.kill(transport._proc.pid, signal.SIGTERM)
        transport._proc.wait(timeout=6)
        self.assert_children_reaped()

    def test_ttl_restart_does_not_overlap_descendants(self):
        transport = self.transport('detached', child_ttl=-1)
        transport.run_operation(lambda operation: None)
        self.wait_for(lambda: any(entry['event'] == 'descendant' for entry in self.events()))
        old_pids = [entry['pid'] for entry in self.events()]
        transport.run_operation(lambda operation: None)
        self.assertTrue(all(not Path(f'/proc/{pid}').exists() for pid in old_pids))
        transport.shutdown()
        self.assert_children_reaped()

    def test_handshake_failure_reaps_child(self):
        transport = self.transport('bad-handshake')
        with self.assertRaises(TransportError):
            transport.run_operation(lambda operation: None)
        self.assert_children_reaped()

    def test_missing_child_reports_only_stderr_marker(self):
        from usage_monitor_for_claude.provider_process_linux import spawn_supervised
        process, control = spawn_supervised(['/missing-synthetic-codex'], dict(os.environ))
        self.addCleanup(control.close)
        stdout, stderr = process.communicate(timeout=6)
        self.assertNotEqual(process.returncode, 0)
        self.assertEqual(stdout, '')
        self.assertEqual(stderr.strip(), 'codex supervisor: spawn failed')

    def test_blocked_stdin_writer_does_not_prevent_cleanup(self):
        transport = self.transport('blocked')
        transport.run_operation(lambda operation: None)
        self.wait_for(lambda: any(entry['event'] == 'ready' for entry in self.events()))
        failures = []
        def write():
            try:
                transport._write_line('x' * 2000000, transport._generation, transport._proc)
            except TransportError:
                failures.append(True)
        writer = threading.Thread(target=write, daemon=True)
        writer.start()
        time.sleep(0.1)
        transport._kill_child()
        writer.join(timeout=2)
        self.assertFalse(writer.is_alive())
        self.assertTrue(failures)
        self.assert_children_reaped()

    def test_monitor_sigterm_and_sigkill_close_control_pipe(self):
        for exit_signal in (signal.SIGTERM, signal.SIGKILL):
            with self.subTest(signal=exit_signal):
                self.state.unlink(missing_ok=True)
                parent = subprocess.Popen([sys.executable, str(PARENT), str(self.state)])
                try:
                    self.wait_for(lambda: any(entry['event'] == 'supervisor' for entry in self.events()))
                    self.wait_for(lambda: any(entry['event'] == 'descendant' for entry in self.events()))
                    os.kill(parent.pid, exit_signal)
                    parent.wait(timeout=6)
                    self.assert_children_reaped()
                finally:
                    if parent.poll() is None:
                        parent.kill()
                        parent.wait()

    def test_pid_identity_change_is_never_signaled(self):
        from usage_monitor_for_claude import _linux_supervisor as supervisor
        identity = supervisor.ProcessIdentity(123, 10, 1, 'S')
        with patch.object(supervisor, '_owned_descendants', return_value={123: supervisor.ProcessIdentity(123, 11, 1, 'S')}), \
             patch.object(supervisor.os, 'pidfd_open', return_value=9), \
             patch.object(supervisor.os, 'close'), \
             patch.object(supervisor.signal, 'pidfd_send_signal') as send:
            supervisor._signal_owned({123: identity}, signal.SIGKILL, 1)
        send.assert_not_called()

    def test_capability_failure_occurs_before_spawn(self):
        from usage_monitor_for_claude import _linux_supervisor as supervisor
        with patch.object(supervisor, '_prepare_supervisor', side_effect=OSError()), \
             patch.object(supervisor.subprocess, 'Popen') as spawn, \
             patch.object(supervisor.sys, 'stderr') as stderr:
            self.assertEqual(supervisor.main(['17', '/synthetic-codex']), 78)
        spawn.assert_not_called()
        self.assertEqual(stderr.write.call_args_list[0].args[0], 'codex supervisor: unavailable')

    def test_child_crash_reaps_stubborn_descendants(self):
        transport = self.transport('crash')
        transport.run_operation(lambda operation: None)
        self.wait_for(lambda: any(entry['event'] == 'descendant' for entry in self.events()))
        transport.run_operation(lambda operation: operation.request('account/read', {}))
        process = transport._proc
        process.wait(timeout=6)
        self.assert_children_reaped()

    def test_cleanup_refusal_prevents_replacement(self):
        transport = self.transport()
        transport.run_operation(lambda operation: None)
        process = transport._proc
        with patch.object(process, 'wait', side_effect=subprocess.TimeoutExpired('synthetic-supervisor', 5)), \
             patch.object(transport, '_spawn') as spawn:
            with self.assertRaisesRegex(TransportError, 'cleanup incomplete'):
                transport.force_restart()
            self.assertIs(transport._proc, process)
            with self.assertRaises(TransportError):
                transport.run_operation(lambda operation: None)
            spawn.assert_not_called()
        with patch.object(app_server_mod.time, 'monotonic', return_value=time.monotonic() + 60):
            transport.shutdown()

    def test_pidfd_is_closed_when_target_disappears(self):
        from usage_monitor_for_claude import _linux_supervisor as supervisor
        identity = supervisor.ProcessIdentity(123, 10, 1, 'S')
        with patch.object(supervisor, '_owned_descendants', return_value={123: identity}), \
             patch.object(supervisor.os, 'pidfd_open', return_value=9), \
             patch.object(supervisor.os, 'close') as close, \
             patch.object(supervisor.signal, 'pidfd_send_signal', side_effect=ProcessLookupError()):
            supervisor._signal_owned({123: identity}, signal.SIGKILL, 1)
        close.assert_called_once_with(9)

    def test_process_name_bytes_do_not_break_identity_read(self):
        from usage_monitor_for_claude import _linux_supervisor as supervisor
        synthetic_stat = b'123 (synthetic-\xff)) S 1 ' + b'0 ' * 17 + b'99 0\n'
        root = Path(self.temporary.name)
        (root / '123').mkdir()
        (root / '123' / 'stat').write_bytes(synthetic_stat)
        with patch.object(supervisor, 'Path', return_value=root):
            identity = supervisor._read_identity(123)
        self.assertIsNotNone(identity)
        self.assertEqual(identity.start_time, 99)
