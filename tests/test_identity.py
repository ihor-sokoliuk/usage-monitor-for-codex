"""
Identity Collision Tests
=========================

Guards against an upstream merge silently reintroducing Claude-monitor
OS identity into the Codex product.
"""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from usage_monitor_for_claude import __version__
from usage_monitor_for_claude import app
from usage_monitor_for_claude.autostart import AUTOSTART_REG_BASE_NAME
from usage_monitor_for_claude.settings import SETTINGS_FILENAME
from usage_monitor_for_claude.single_instance import _MUTEX_BASE_NAME, _PID_MAPPING_BASE_NAME


class TestIdentityConstants(unittest.TestCase):
    def test_codex_values(self):
        self.assertEqual(_MUTEX_BASE_NAME, 'UsageMonitorForCodex_SingleInstance')
        self.assertEqual(_PID_MAPPING_BASE_NAME, 'UsageMonitorForCodex_HolderPID')
        self.assertEqual(AUTOSTART_REG_BASE_NAME, 'UsageMonitorForCodex')
        self.assertEqual(SETTINGS_FILENAME, 'usage-monitor-for-codex-settings.json')

    def test_runtime_pystray_icon_name(self):
        with patch.object(app, 'UsageCache'), \
             patch.object(app, 'taskbar_uses_light_theme', return_value=False), \
             patch.object(app, 'create_icon_image'), \
             patch.object(app.pystray, 'Icon') as icon:
            app.UsageMonitorForCodex()
        self.assertEqual(icon.call_args.args[0], 'usage_monitor_for_codex')


class TestBuildIdentity(unittest.TestCase):
    def test_version_metadata_matches_release(self):
        root = Path(__file__).parent.parent
        version = (root / 'version_info.py').read_text(encoding='utf-8')

        self.assertEqual(__version__, '1.20.0')
        self.assertIn('filevers=(1, 20, 0, 0)', version)
        self.assertIn('prodvers=(1, 20, 0, 0)', version)
        self.assertIn("StringStruct('FileVersion', '1.20.0.0')", version)
        self.assertIn("StringStruct('ProductVersion', '1.20.0.0')", version)

    def test_codex_build_metadata_has_no_claude_product_identity(self):
        root = Path(__file__).parent.parent
        spec = (root / 'usage_monitor_for_codex.spec').read_text(encoding='utf-8')
        build = (root / 'build.py').read_text(encoding='utf-8')
        version = (root / 'version_info.py').read_text(encoding='utf-8')
        combined = '\n'.join((spec, build, version))
        self.assertIn('UsageMonitorForCodex', combined)
        self.assertIn('UsageMonitorForCodex.exe', combined)
        self.assertIn('usage_monitor_for_codex.ico', spec)
        self.assertNotIn('UsageMonitorForClaude', combined)
