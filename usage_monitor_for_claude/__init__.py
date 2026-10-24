"""
Usage Monitor for Codex
=======================

Displays the current Codex usage as a system tray icon.
Left-click the icon to see a detailed usage popup.

Reads account and rate-limit data from the local ``codex app-server``
(requires the Codex CLI, signed in via ``codex login``). Respects
``CODEX_HOME`` if set, otherwise defaults to ``~/.codex/``.
"""
from __future__ import annotations

__version__ = '1.24.0'
