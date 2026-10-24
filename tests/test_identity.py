"""
Identity Collision Tests
=========================

Guards against an upstream merge silently reintroducing Claude-monitor
OS identity into the Codex product.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from usage_monitor_for_claude import app
from usage_monitor_for_claude.settings import SETTINGS_FILENAME
if sys.platform == 'win32':
    from usage_monitor_for_claude.platforms import instance_win32 as instance_backend
    from usage_monitor_for_claude.platforms import win32 as desktop_backend
else:
    from usage_monitor_for_claude.platforms import instance_linux as instance_backend
    from usage_monitor_for_claude.platforms import linux as desktop_backend


class TestIdentityConstants(unittest.TestCase):
    def test_codex_values(self):
        if sys.platform == 'win32':
            self.assertEqual(instance_backend._MUTEX_BASE_NAME, 'UsageMonitorForCodex_SingleInstance')
            self.assertEqual(instance_backend._PID_MAPPING_BASE_NAME, 'UsageMonitorForCodex_HolderPID')
            self.assertEqual(desktop_backend.AUTOSTART_REG_BASE_NAME, 'UsageMonitorForCodex')
            self.assertEqual(desktop_backend.APP_USER_MODEL_ID, 'UsageMonitorForCodex.Desktop')
        else:
            self.assertEqual(instance_backend._LOCK_BASE_NAME, 'usage-monitor-for-codex')
            self.assertEqual(desktop_backend.AUTOSTART_BASE_NAME, 'usage-monitor-for-codex')
            self.assertEqual(desktop_backend.APPLICATION_NAME, 'Usage Monitor for Codex')
        self.assertEqual(SETTINGS_FILENAME, 'usage-monitor-for-codex-settings.json')

    def test_runtime_pystray_icon_name(self):
        with patch.object(app, 'UsageCache'), \
             patch.object(app, 'taskbar_uses_light_theme', return_value=False), \
             patch.object(app, 'create_icon_image'), \
             patch.object(app.pystray, 'Icon') as icon:
            app.UsageMonitorForCodex()
        self.assertEqual(icon.call_args.args[0], 'usage_monitor_for_codex')


class TestBuildIdentity(unittest.TestCase):
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


class TestSourceDistributionIdentity(unittest.TestCase):
    def test_notification_asset_is_the_codex_icon(self):
        root = Path(__file__).resolve().parent.parent
        self.assertEqual(
            (root / 'usage_monitor_for_claude' / 'notification_logo.ico').read_bytes(),
            (root / 'usage_monitor_for_codex.ico').read_bytes(),
        )

    def test_source_launcher_uses_codex_product_name(self):
        root = Path(__file__).resolve().parent.parent
        self.assertTrue((root / 'usage-monitor-for-codex').is_file())
        self.assertFalse((root / 'usage-monitor-for-claude').exists())
        launcher = (root / 'usage-monitor-for-codex').read_text(encoding='utf-8')
        self.assertIn('-m usage_monitor_for_claude', launcher)
        self.assertNotIn('Usage Monitor for Claude', launcher)

    def test_removed_provider_http_dependencies_stay_absent(self):
        root = Path(__file__).resolve().parent.parent
        requirements = (root / 'requirements.txt').read_text(encoding='utf-8').lower()
        self.assertNotIn('requests', requirements)
        self.assertNotIn('truststore', requirements)

    def test_release_workflow_uses_fork_identity_and_namespace(self):
        root = Path(__file__).resolve().parent.parent
        workflow = (root / '.github' / 'workflows' / 'release.yml').read_text(encoding='utf-8')
        self.assertIn('codex-v*', workflow)
        self.assertIn('UsageMonitorForCodex.exe', workflow)
        self.assertNotIn('UsageMonitorForClaude', workflow)
        self.assertFalse((root / '.github' / 'workflows' / 'winget.yml').exists())
        self.assertFalse((root / '.github' / 'workflows' / 'winget-watch.yml').exists())
