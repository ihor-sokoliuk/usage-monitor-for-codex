"""Compatibility exports for platform autostart behavior."""
from __future__ import annotations

import unittest

from usage_monitor_for_claude import autostart, platforms


class TestAutostartCompatibility(unittest.TestCase):
    def test_exports_selected_platform_implementation(self):
        for name in ('autostart_supported', 'is_autostart_enabled', 'set_autostart', 'sync_autostart_path'):
            with self.subTest(name=name):
                self.assertIs(getattr(autostart, name), getattr(platforms, name))
