"""Exercise Codex quota behavior through the upstream display controls."""
from __future__ import annotations

import unittest

from usage_monitor_for_claude.formatting import expand_popup_fields, popup_label


class TestCodexQuotaExclusions(unittest.TestCase):
    def test_wildcard_exclusion_preserves_durationless_quota(self):
        usage = {
            'five_hour': {'utilization': 10, 'resets_at': ''},
            'seven_day': {'utilization': 30, 'resets_at': ''},
            'custom_limit': {'utilization': 0, 'resets_at': ''},
        }
        self.assertEqual(expand_popup_fields(['*', '-seven_day'], usage), ['five_hour', 'custom_limit'])

    def test_exclusion_wins_over_explicit_inclusion_in_any_position(self):
        usage = {'five_hour': {'utilization': 0, 'resets_at': ''}}
        for fields in (['five_hour', '*', '-five_hour'], ['-five_hour', '*', 'five_hour']):
            with self.subTest(fields=fields):
                self.assertEqual(expand_popup_fields(fields, usage), [])

    def test_model_label_survives_normalized_field_name(self):
        self.assertIn('Codex Mini', popup_label('five_hour_codex_mini', 'Codex Mini'))


if __name__ == '__main__':
    unittest.main()
