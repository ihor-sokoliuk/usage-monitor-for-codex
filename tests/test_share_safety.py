"""Tests for sanitizing output from the opt-in live integration utility."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from tests.integration.probe_live_app_server import sanitize


class TestLiveOutputSanitization(unittest.TestCase):
    def test_removes_account_metrics_credentials_and_user_paths(self):
        home = str(Path.home())
        source = {
            'account': {
                'type': 'chatgpt',
                'email': 'real-person@example.invalid',
                'name': 'Real Person',
                'planType': 'private-plan',
            },
            'rateLimits': {
                'usedPercent': 78.0,
                'resetsAt': 1893456000,
                'limitId': 'private-model-limit',
                'credits': {'hasCredits': True, 'unlimited': False, 'balance': '123.45'},
            },
            'refreshToken': 'secret-value',
            'codexHome': f'{home}\\.codex',
            'message': f'loaded state below {home}\\.codex',
        }

        result = sanitize(source)
        encoded = json.dumps(result)

        self.assertEqual(result['account']['type'], 'chatgpt')
        for private_value in (
            'real-person@example.invalid', 'Real Person', 'private-plan',
            '78.0', '1893456000', 'private-model-limit', '123.45',
            'secret-value', home,
        ):
            self.assertNotIn(private_value, encoded)
        self.assertIn('<redacted>', encoded)
        self.assertIn('~', result['message'])


if __name__ == '__main__':
    unittest.main()
