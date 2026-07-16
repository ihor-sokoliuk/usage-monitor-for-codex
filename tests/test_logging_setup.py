"""Tests for the always-on rotating application log."""
from __future__ import annotations

import logging
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from usage_monitor_for_claude.logging_setup import (
    LOG_FILENAME,
    application_log_filename,
    application_directory,
    configure_logging,
)


class TestApplicationDirectory(unittest.TestCase):
    def test_frozen_build_uses_executable_directory(self):
        with TemporaryDirectory() as tmp:
            executable = Path(tmp) / 'UsageMonitorForCodex.exe'
            with patch.object(sys, 'frozen', True, create=True), \
                 patch.object(sys, 'executable', str(executable)):
                self.assertEqual(application_directory(), Path(tmp).resolve())

    def test_source_build_uses_project_root(self):
        expected = Path(__file__).resolve().parent.parent
        self.assertEqual(application_directory(), expected)


class TestApplicationLogFilename(unittest.TestCase):
    def test_default_home_keeps_legacy_filename(self):
        with patch('usage_monitor_for_claude.logging_setup.config_dir_suffix', return_value=''):
            self.assertEqual(application_log_filename(), LOG_FILENAME)

    def test_custom_home_gets_distinct_filename(self):
        with patch('usage_monitor_for_claude.logging_setup.config_dir_suffix', return_value='_abc123def456'):
            self.assertEqual(application_log_filename(), 'usage-monitor-for-codex_abc123def456.log')


class TestConfigureLogging(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(
            configure_logging,
            verbose=False,
            max_bytes=1024,
            backup_count=1,
            disable=True,
        )

    def _path(self) -> Path:
        return Path(self._tmp.name) / LOG_FILENAME

    def test_creates_log_immediately_and_writes_info(self):
        path = self._path()
        returned = configure_logging(
            verbose=False, max_bytes=1024, backup_count=2, path=path,
        )
        logging.getLogger('test.monitor').info('provider request completed')
        for handler in logging.getLogger().handlers:
            handler.flush()

        self.assertEqual(returned, path)
        self.assertTrue(path.is_file())
        self.assertIn('provider request completed', path.read_text(encoding='utf-8'))

    def test_rotates_at_configured_size(self):
        path = self._path()
        configure_logging(verbose=False, max_bytes=160, backup_count=2, path=path)
        logger = logging.getLogger('test.rotation')
        for index in range(30):
            logger.info('rotation record %02d %s', index, 'x' * 40)
        for handler in logging.getLogger().handlers:
            handler.flush()

        self.assertTrue(path.is_file())
        self.assertTrue(Path(f'{path}.1').is_file())
        self.assertFalse(Path(f'{path}.3').exists())

    def test_verbose_adds_console_handler(self):
        configure_logging(
            verbose=True,
            max_bytes=1024,
            backup_count=1,
            path=self._path(),
        )
        owned = [
            handler for handler in logging.getLogger().handlers
            if getattr(handler, '_usage_monitor_handler', False)
        ]
        self.assertEqual(len(owned), 2)

    def test_non_verbose_has_only_file_handler(self):
        configure_logging(
            verbose=False,
            max_bytes=1024,
            backup_count=1,
            path=self._path(),
        )
        owned = [
            handler for handler in logging.getLogger().handlers
            if getattr(handler, '_usage_monitor_handler', False)
        ]
        self.assertEqual(len(owned), 1)

    def test_reconfiguration_does_not_duplicate_handlers(self):
        path = self._path()
        configure_logging(verbose=False, max_bytes=1024, backup_count=1, path=path)
        configure_logging(verbose=False, max_bytes=1024, backup_count=1, path=path)
        owned = [
            handler for handler in logging.getLogger().handlers
            if getattr(handler, '_usage_monitor_handler', False)
        ]
        self.assertEqual(len(owned), 1)

    def test_implicit_path_uses_per_home_filename(self):
        with patch('usage_monitor_for_claude.logging_setup.application_directory', return_value=Path(self._tmp.name)), \
             patch('usage_monitor_for_claude.logging_setup.config_dir_suffix', return_value='_abc123def456'):
            path = configure_logging(verbose=False, max_bytes=1024, backup_count=1)
        self.assertEqual(path.name, 'usage-monitor-for-codex_abc123def456.log')
        self.assertTrue(path.is_file())

    def test_log_formatter_redacts_home_case_and_separator_variants(self):
        path = self._path()
        home = str(Path.home())
        configure_logging(verbose=False, max_bytes=4096, backup_count=1, path=path)
        logging.getLogger('test.privacy').error(
            'paths: %s and %s', home.lower(), home.replace('\\', '/'),
        )
        for handler in logging.getLogger().handlers:
            handler.flush()
        text = path.read_text(encoding='utf-8')
        self.assertNotIn(home.casefold(), text.casefold())
        self.assertIn('~', text)


if __name__ == '__main__':
    unittest.main()
