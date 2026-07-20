"""
DPI Tests
=========

Unit tests for process DPI-awareness startup compatibility.
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from usage_monitor_for_claude.dpi import set_process_dpi_awareness


class TestSetProcessDpiAwareness(unittest.TestCase):
    """Tests for the optional Per-Monitor V2 startup call."""

    def test_sets_per_monitor_v2_when_api_is_available(self):
        mock_ctypes = MagicMock()

        with patch('usage_monitor_for_claude.dpi.ctypes', mock_ctypes):
            set_process_dpi_awareness()

        mock_ctypes.c_ssize_t.assert_called_once_with(-4)
        mock_ctypes.windll.user32.SetProcessDpiAwarenessContext.assert_called_once_with(
            mock_ctypes.c_ssize_t.return_value,
        )

    def test_missing_api_falls_back_without_error(self):
        mock_ctypes = SimpleNamespace(
            c_ssize_t=MagicMock(),
            windll=SimpleNamespace(user32=object()),
        )

        with patch('usage_monitor_for_claude.dpi.ctypes', mock_ctypes):
            set_process_dpi_awareness()

        mock_ctypes.c_ssize_t.assert_not_called()


if __name__ == '__main__':
    unittest.main()
