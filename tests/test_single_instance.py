"""Compatibility exports for the platform instance guard."""
from __future__ import annotations

import unittest

from usage_monitor_for_claude import single_instance
from usage_monitor_for_claude.platforms import instance


class TestInstanceCompatibility(unittest.TestCase):
    def test_exports_selected_platform_implementation(self):
        self.assertIs(single_instance.ensure_single_instance, instance.ensure_single_instance)
        self.assertIs(single_instance.release_instance_lock, instance.release_instance_lock)
