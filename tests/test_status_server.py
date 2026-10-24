"""
Status Endpoint Tests
=====================

Contract, cached-data isolation, settings, and listener lifecycle coverage.
"""
from __future__ import annotations

import http.client
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from usage_monitor_for_claude import app as app_module, settings
from usage_monitor_for_claude.status_server import StatusServer, build_snapshot


def make_cache() -> MagicMock:
    """Return a cached synthetic quota with private profile data."""
    cache = MagicMock()
    cache.snapshot = SimpleNamespace(usage={'five_hour': {'utilization': 42.2, 'resets_at': None}},
                                     last_success_time=None, last_error=None,
                                     profile={'email': 'synthetic@example.invalid'})
    return cache


class TestStatusContract(unittest.TestCase):
    """The endpoint projects only documented fields from one cache snapshot."""

    def test_only_sanitized_cached_data_is_exposed(self) -> None:
        """Profiles and raw errors never enter the versioned response."""
        cache = make_cache()
        cache.snapshot.last_error = 'sensitive synthetic error'
        data = build_snapshot(cache, 'codex', 'Codex')
        self.assertEqual(set(data), {'schema', 'generated_at', 'providers'})
        generated_at = datetime.fromisoformat(data['generated_at'])
        self.assertEqual(generated_at.utcoffset(), timezone.utc.utcoffset(None))
        self.assertEqual(set(data['providers']), {'codex'})
        provider = data['providers']['codex']
        self.assertEqual(set(provider), {'display_name', 'windows', 'stale', 'error'})
        self.assertEqual(data['schema'], 1)
        self.assertEqual(provider['windows'], {'five_hour': {'utilization': 42, 'resets_at': ''}})
        self.assertIsNone(provider['stale'])
        self.assertEqual(provider['error'], 'Usage data unavailable.')
        self.assertNotIn('synthetic', json.dumps(data))
        cache.update.assert_not_called()
        cache.ensure_profile.assert_not_called()

    def test_empty_malformed_and_stale_state(self) -> None:
        """Malformed entries stay JSON-safe and staleness has an exact boundary."""
        cache = make_cache()
        for usage in ({}, None, {'null': None, 'raw': [], 'window': {'utilization': float('nan')}}):
            cache.snapshot.usage = usage
            data = build_snapshot(cache, 'codex', 'Codex')
            json.dumps(data, allow_nan=False)
        cache.snapshot.last_success_time = 100
        with patch('usage_monitor_for_claude.status_server.time.time', return_value=100 + 3 * settings.POLL_INTERVAL):
            self.assertFalse(build_snapshot(cache, 'codex', 'Codex')['providers']['codex']['stale'])
        with patch('usage_monitor_for_claude.status_server.time.time', return_value=101 + 3 * settings.POLL_INTERVAL):
            self.assertTrue(build_snapshot(cache, 'codex', 'Codex')['providers']['codex']['stale'])

    def test_invalid_utilization_is_json_safe(self) -> None:
        """Nonfinite, huge, boolean, and nonnumeric values are normalized to zero."""
        cache = make_cache()
        for value in (float('nan'), float('inf'), -float('inf'), 10 ** 1000, True, None, '42'):
            with self.subTest(value=value):
                cache.snapshot.usage = {'window': {'utilization': value}}
                data = build_snapshot(cache, 'codex', 'Codex')
                self.assertEqual(data['providers']['codex']['windows'], {'window': {'utilization': 0, 'resets_at': ''}})
                json.dumps(data, allow_nan=False)

    def test_dynamic_windows_exclude_raw_metadata(self) -> None:
        """Arbitrary duration and durationless windows expose only quota values."""
        cache = make_cache()
        cache.snapshot.usage = {
            '90_minute_model': {'utilization': 17.8, 'resets_at': '2026-01-01T12:00:00Z', 'raw': 'private synthetic payload'},
            'quota_other': {'utilization': 7.1, 'resets_at': None, 'limit_name': 'synthetic model'},
            'null_window': None,
            'credits': {'balance': 123},
            'extra_usage': {'is_enabled': True, 'used_credits': 900},
        }
        with patch('usage_monitor_for_claude.cache.fetch_provider_data') as fetch:
            windows = build_snapshot(cache, 'codex', 'Codex')['providers']['codex']['windows']
        self.assertEqual(windows, {
            '90_minute_model': {'utilization': 18, 'resets_at': '2026-01-01T12:00:00Z'},
            'quota_other': {'utilization': 7, 'resets_at': ''},
        })
        fetch.assert_not_called()

    def test_repeated_start_keeps_one_listener(self) -> None:
        """Starting an active owner again does not replace or leak its socket."""
        server = StatusServer(make_cache(), 'codex', 'Codex', 0)
        self.addCleanup(server.shutdown)
        server.start()
        listener = server._server
        server.start()
        self.assertIs(server._server, listener)

    def test_loopback_paths_methods_and_shutdown(self) -> None:
        """Only documented GET paths work, and shutdown releases the occupied port."""
        fetch_patch = patch('usage_monitor_for_claude.cache.fetch_provider_data')
        fetch = fetch_patch.start()
        self.addCleanup(fetch_patch.stop)
        cache = make_cache()
        server = StatusServer(cache, 'codex', 'Codex', 0)
        server.start()
        self.addCleanup(server.shutdown)
        assert server._server is not None
        self.assertEqual(server._server.server_address[0], '127.0.0.1')
        port = server._server.server_port
        for method, path, expected in [('GET', '/', 200), ('GET', '/usage', 200), ('GET', '/unknown', 404), ('GET', '/usage?x=1', 404),
                                       ('POST', '/usage', 405), ('HEAD', '/usage', 405), ('OPTIONS', '/', 405),
                                       ('PUT', '/', 405), ('PATCH', '/', 405), ('DELETE', '/', 405), ('TRACE', '/', 405),
                                       ('CONNECT', '/', 405), ('UNKNOWN', '/', 405)]:
            with self.subTest(method=method, path=path):
                connection = http.client.HTTPConnection('127.0.0.1', port, timeout=2)
                try:
                    connection.request(method, path)
                    response = connection.getresponse()
                    self.assertEqual(response.status, expected)
                    self.assertIsNone(response.getheader('Access-Control-Allow-Origin'))
                    if expected == 405:
                        self.assertEqual(response.getheader('Allow'), 'GET')
                    if expected == 200:
                        self.assertEqual(response.getheader('Content-Type'), 'application/json')
                        self.assertEqual(response.getheader('Cache-Control'), 'no-store')
                        data = json.loads(response.read())
                        self.assertEqual(set(data['providers']), {'codex'})
                        self.assertEqual(data['providers']['codex']['windows']['five_hour']['utilization'], 42)
                    else:
                        response.read()
                finally:
                    connection.close()
        cache.update.assert_not_called()
        cache.ensure_profile.assert_not_called()
        fetch.assert_not_called()
        conflict = StatusServer(cache, 'codex', 'Codex', port)
        with self.assertRaises(OSError):
            conflict.start()
        server.shutdown()
        server.shutdown()
        replacement = StatusServer(cache, 'codex', 'Codex', port)
        replacement.start()
        replacement.shutdown()

    def test_settings_defaults_and_validation(self) -> None:
        """Invalid overrides report the affected setting and settings filename."""
        self.assertFalse(settings.STATUS_SERVER_ENABLED)
        self.assertEqual(settings.STATUS_SERVER_PORT, 45457)
        for value in (0, 1023, 65536, True, '45457'):
            with self.subTest(value=value), patch('usage_monitor_for_claude.settings.show_warning_box') as warning:
                self.assertNotIn('status_server_port', settings._validate({'status_server_port': value}, Path('synthetic.json')))
                warning.assert_called_once()
                self.assertIn('status_server_port', warning.call_args.args[0])
                self.assertIn('synthetic.json', warning.call_args.args[0])
        for value in (1024, 65535):
            with self.subTest(value=value), patch('usage_monitor_for_claude.settings.show_warning_box') as warning:
                self.assertEqual(settings._validate({'status_server_port': value}, Path('synthetic.json'))['status_server_port'], value)
                warning.assert_not_called()
        with patch('usage_monitor_for_claude.settings.show_warning_box') as warning:
            self.assertNotIn('status_server_enabled', settings._validate({'status_server_enabled': 'true'}, Path('synthetic.json')))
            warning.assert_called_once()
            self.assertIn('status_server_enabled', warning.call_args.args[0])


class TestStatusLifecycle(unittest.TestCase):
    """The endpoint follows the application's tray lifecycle without owning it."""

    def make_app(self) -> app_module.UsageMonitorForCodex:
        """Create the minimal application state needed by run and restart."""
        app = object.__new__(app_module.UsageMonitorForCodex)
        app.cache, app.icon = make_cache(), MagicMock()
        return app

    def test_disabled_by_default(self) -> None:
        """An ordinary startup creates no endpoint listener."""
        app = self.make_app()
        with patch.object(app_module, 'StatusServer') as server, patch.object(app_module, 'STATUS_SERVER_ENABLED', False):
            app.run()
        server.assert_not_called()
        app.icon.run.assert_called_once()

    def test_listener_is_closed_on_normal_exit_and_failure(self) -> None:
        """The listener closes whether the tray exits normally or raises."""
        for failure in (None, RuntimeError('synthetic tray failure')):
            app = self.make_app()
            app.icon.run.side_effect = failure
            with patch.object(app_module, 'StatusServer') as server, patch.object(app_module, 'STATUS_SERVER_ENABLED', True):
                if failure:
                    with self.assertRaises(RuntimeError):
                        app.run()
                else:
                    app.run()
                server.return_value.start.assert_called_once()
                server.return_value.shutdown.assert_called_once()

    def test_restart_releases_listener_before_returning(self) -> None:
        """Restart exits the tray run and releases the listener before relaunch."""
        app = self.make_app()
        app.icon.run.side_effect = lambda **_kwargs: app.on_restart()
        with patch.object(app_module, 'StatusServer') as server, patch.object(app_module, 'STATUS_SERVER_ENABLED', True):
            app.run()
        self.assertTrue(app.restart_requested)
        self.assertFalse(app.running)
        app.icon.stop.assert_called_once()
        server.return_value.shutdown.assert_called_once()

    def test_port_conflict_does_not_stop_tray(self) -> None:
        """A failed bind leaves the application usable without an endpoint."""
        app = self.make_app()
        with patch.object(app_module, 'StatusServer') as server, patch.object(app_module, 'STATUS_SERVER_ENABLED', True):
            server.return_value.start.side_effect = OSError('synthetic bind failure')
            app.run()
        app.icon.run.assert_called_once()
