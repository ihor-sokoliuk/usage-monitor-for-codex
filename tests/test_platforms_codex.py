"""Codex-specific platform and display regressions."""
from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from usage_monitor_for_claude import popup, tray_icon, verbose
from usage_monitor_for_claude.cache import CacheSnapshot
from usage_monitor_for_claude.platforms import linux


class TestCodexPopupPayload(unittest.TestCase):
    def test_provider_model_label_and_durationless_quota(self):
        usage = {'quota_bengalfox': {'utilization': 17, 'resets_at': '', 'limit_name': 'gpt-5.2-codex-sonic'}}
        snap = CacheSnapshot(usage=usage, profile=None, last_success_time=None, refreshing=False, last_error=None, version=0)
        with patch.object(popup, 'POPUP_FIELDS', ['*']):
            result = popup._snapshot_to_dict(snap, installations=[])
        self.assertEqual(len(result['usage']), 1)
        self.assertIn('GPT-5.2-Codex-Sonic', result['usage'][0]['label'])
        self.assertEqual(result['usage'][0]['dividers'], [])
        self.assertIsNone(result['usage'][0]['marker_rel'])

    def test_duration_quota_uses_provider_model_name(self):
        usage = {'seven_day_codex_bengalfox': {
            'utilization': 0, 'resets_at': '', 'limit_name': 'gpt-5.2-codex-sonic',
        }}
        with patch.object(popup, 'POPUP_FIELDS', ['*']):
            entries = popup._usage_entries(usage)
        self.assertEqual(entries[0][0], 'Weekly (GPT-5.2-Codex-Sonic)')

    def test_provider_credit_metadata_never_renders_billing(self):
        snap = CacheSnapshot(
            usage={'five_hour': {'utilization': 10, 'resets_at': ''},
                   'credits': {'balance': 123},
                   'extra_usage': {'is_enabled': True, 'used_credits': 100, 'monthly_limit': 1000}},
            profile=None, last_success_time=None, refreshing=False, last_error=None, version=0,
        )
        result = popup._snapshot_to_dict(snap, installations=[])
        self.assertIsNone(result['extra'])
        self.assertNotIn('prepaid', result)


class TestCodexTray(unittest.TestCase):
    def test_weekly_only_icon_draws_one_centered_bar(self):
        with patch.object(tray_icon, '_draw_usage_bar') as draw:
            tray_icon.create_icon_image(None, 67)
        draw.assert_called_once()
        self.assertEqual(draw.call_args.args[2], 67)
        expected = tray_icon.ICON_SIZE - tray_icon.BAR_HEIGHT - (tray_icon.BAR_HEIGHT + tray_icon.BAR_GAP) // 2
        self.assertEqual(draw.call_args.args[1], expected)

    def test_single_available_limit_bar_count_is_preserved(self):
        with patch.object(tray_icon, '_draw_usage_bar') as draw:
            tray_icon.create_icon_image(67, 0, bar_count=1)
        draw.assert_called_once()
        self.assertEqual(draw.call_args.args[2], 67)

    def test_no_available_limits_draws_no_bars(self):
        with patch.object(tray_icon, '_draw_usage_bar') as draw:
            tray_icon.create_icon_image(0, 0, bar_count=0)
        draw.assert_not_called()

    def test_numbers_weekly_only_draws_one_centered_value(self):
        with patch.object(tray_icon, 'ICON_STYLE', 'numbers'), patch.object(tray_icon, '_draw_centered_text') as draw:
            tray_icon.create_icon_image(None, 67)
        draw.assert_called_once()
        self.assertEqual(draw.call_args.args[1], '67')

    def test_numbers_single_bar_count_has_no_phantom_second_row(self):
        with patch.object(tray_icon, 'ICON_STYLE', 'numbers'), patch.object(tray_icon, '_draw_centered_text') as draw:
            tray_icon.create_icon_image(67, 100, bar_count=1)
        draw.assert_called_once()
        self.assertEqual(draw.call_args.args[1], '67')

    def test_zero_state_has_codex_prompt(self):
        self.assertEqual(tray_icon.ZERO_STATE_GLYPH, '>_')


class TestCodexDiagnostics(unittest.TestCase):
    def test_no_credentials_probe_is_exposed(self):
        self.assertFalse(hasattr(verbose, '_credentials_status'))
        source = Path(verbose.__file__).read_text(encoding='utf-8')
        self.assertNotIn('.credentials.json', source)
        self.assertNotIn('auth.json', source)

    def test_diagnostic_capture_preserved(self):
        self.assertEqual(verbose.capture_diagnostics(lambda: print('sanitized diagnostic')), 'sanitized diagnostic\n')

    def test_unknown_linux_lock_state_stays_unknown(self):
        with patch.object(linux, '_call_session_method', return_value=None):
            self.assertIsNone(linux.is_workstation_locked())


if __name__ == '__main__':
    unittest.main()
