"""Regression tests for the attributed upstream Windows hook fix."""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import unittest
from typing import Any, cast

from usage_monitor_for_claude.popup import _HOOKPROC


class TestHookSignatures(unittest.TestCase):
    """Tests for the Win32 signatures behind the dismiss watch.

    A low-level hook procedure returns ``LRESULT``, which is pointer-sized.
    Declared narrower, the upper half of the return register is left
    undefined on 64-bit Windows, and any nonzero value makes Windows drop the
    keystroke or click as consumed.
    """

    def test_hook_proc_returns_pointer_sized_lresult(self):
        """Regression: a ``c_long`` return type swallowed keystrokes system-wide while the popup was open."""
        result_type = _HOOKPROC._restype_
        assert result_type is not None
        self.assertEqual(ctypes.sizeof(cast(Any, result_type)), ctypes.sizeof(ctypes.c_void_p))

    def test_hook_proc_takes_code_wparam_lparam(self):
        """The hook procedure signature matches ``HOOKPROC``."""
        self.assertEqual(_HOOKPROC._argtypes_, (ctypes.c_int, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM))

    def test_call_next_hook_returns_pointer_sized_lresult(self):
        """The next hook's result passes through untruncated."""
        result_type = ctypes.windll.user32.CallNextHookEx.restype
        assert result_type is not None
        self.assertEqual(ctypes.sizeof(cast(Any, result_type)), ctypes.sizeof(ctypes.c_void_p))

    def test_hook_handles_are_pointer_sized(self):
        """Hook handles are not truncated to ``c_int`` on 64-bit."""
        for name in ('SetWindowsHookExW', 'SetWinEventHook'):
            with self.subTest(name=name):
                self.assertEqual(ctypes.sizeof(getattr(ctypes.windll.user32, name).restype), ctypes.sizeof(ctypes.c_void_p))
