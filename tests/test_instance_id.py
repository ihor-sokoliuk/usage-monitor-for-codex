"""
Instance Identity Tests
========================

Unit tests for --codex-home parsing and per-instance name suffixes.
"""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from usage_monitor_for_claude.instance_id import config_dir_suffix, effective_config_dir, is_default_config_dir, parse_codex_home


class TestParseConfigDir(unittest.TestCase):
    """Tests for parse_codex_home()."""

    def test_equals_form(self):
        self.assertEqual(parse_codex_home(['app.exe', r'--codex-home=C:\dir']), r'C:\dir')

    def test_space_form(self):
        self.assertEqual(parse_codex_home(['app.exe', '--codex-home', r'C:\dir']), r'C:\dir')

    def test_absent_flag_returns_none(self):
        self.assertIsNone(parse_codex_home(['app.exe', '--verbose']))

    def test_flag_without_value_returns_none(self):
        self.assertIsNone(parse_codex_home(['app.exe', '--codex-home']))

    def test_empty_value_returns_none(self):
        self.assertIsNone(parse_codex_home(['app.exe', '--codex-home=']))

    def test_strips_surrounding_quotes(self):
        self.assertEqual(parse_codex_home(['app.exe', '--codex-home="C:\\dir"']), r'C:\dir')

    def test_strips_trailing_quote_from_cmd_quoting(self):
        """cmd.exe turns --codex-home="C:\\dir\\" into a value with a trailing quote."""
        self.assertEqual(parse_codex_home(['app.exe', '--codex-home=C:\\dir\\"']), r'C:\dir')

    def test_strips_trailing_backslash(self):
        self.assertEqual(parse_codex_home(['app.exe', '--codex-home=C:\\dir\\']), r'C:\dir')

    def test_expands_environment_variables(self):
        """%VAR% syntax works even from shells that do not expand it (PowerShell)."""
        with patch.dict('os.environ', {'USERPROFILE': r'C:\Users\test'}):
            result = parse_codex_home(['app.exe', '--codex-home=%USERPROFILE%\\.codex-second'])
        self.assertEqual(result, r'C:\Users\test\.codex-second')

    def test_expands_tilde(self):
        with patch.dict('os.environ', {'USERPROFILE': r'C:\Users\test'}):
            result = parse_codex_home(['app.exe', '--codex-home=~/.codex-second'])
        self.assertEqual(result, r'C:\Users\test\.codex-second')

    def test_last_occurrence_wins(self):
        argv = ['app.exe', '--codex-home=C:\\first', '--codex-home=C:\\second']
        self.assertEqual(parse_codex_home(argv), r'C:\second')

    def test_drive_root_keeps_separator(self):
        self.assertEqual(parse_codex_home(['app.exe', '--codex-home=D:\\']), 'D:\\')

    def test_drive_root_with_cmd_trailing_quote(self):
        self.assertEqual(parse_codex_home(['app.exe', '--codex-home=D:\\"']), 'D:\\')

    def test_drive_root_forward_slash(self):
        self.assertEqual(parse_codex_home(['app.exe', '--codex-home=D:/']), 'D:\\')


class TestConfigDirSuffix(unittest.TestCase):
    """Tests for config_dir_suffix() and is_default_config_dir()."""

    def test_default_when_env_unset(self):
        with patch.dict('os.environ', {}, clear=False):
            import os
            os.environ.pop('CODEX_HOME', None)
            self.assertTrue(is_default_config_dir())
            self.assertEqual(config_dir_suffix(), '')

    def test_default_when_env_points_to_home_claude(self):
        with TemporaryDirectory() as home_tmp:
            claude_dir = Path(home_tmp) / '.codex'
            claude_dir.mkdir()
            with patch.object(Path, 'home', return_value=Path(home_tmp)), \
                 patch.dict('os.environ', {'CODEX_HOME': str(claude_dir)}):
                self.assertTrue(is_default_config_dir())
                self.assertEqual(config_dir_suffix(), '')

    def test_custom_dir_produces_suffix(self):
        with TemporaryDirectory() as config_tmp:
            with patch.dict('os.environ', {'CODEX_HOME': config_tmp}):
                self.assertFalse(is_default_config_dir())
                suffix = config_dir_suffix()
        self.assertTrue(suffix.startswith('_'))
        self.assertEqual(len(suffix), 13)

    def test_suffix_stable_across_casing_and_trailing_slash(self):
        with TemporaryDirectory() as config_tmp:
            with patch.dict('os.environ', {'CODEX_HOME': config_tmp}):
                suffix_plain = config_dir_suffix()
            with patch.dict('os.environ', {'CODEX_HOME': config_tmp.upper() + '\\'}):
                suffix_variant = config_dir_suffix()
        self.assertEqual(suffix_plain, suffix_variant)

    def test_different_dirs_produce_different_suffixes(self):
        with TemporaryDirectory() as dir_a, TemporaryDirectory() as dir_b:
            with patch.dict('os.environ', {'CODEX_HOME': dir_a}):
                suffix_a = config_dir_suffix()
            with patch.dict('os.environ', {'CODEX_HOME': dir_b}):
                suffix_b = config_dir_suffix()
        self.assertNotEqual(suffix_a, suffix_b)

    def test_effective_config_dir_resolves_env_value(self):
        with TemporaryDirectory() as config_tmp:
            with patch.dict('os.environ', {'CODEX_HOME': config_tmp}):
                self.assertEqual(effective_config_dir(), Path(config_tmp).resolve())


if __name__ == '__main__':
    unittest.main()
