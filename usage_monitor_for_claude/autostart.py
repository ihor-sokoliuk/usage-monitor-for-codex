"""Platform-specific application autostart compatibility exports."""
from __future__ import annotations

from .platforms import autostart_supported, is_autostart_enabled, set_autostart, sync_autostart_path

__all__ = ['autostart_supported', 'is_autostart_enabled', 'set_autostart', 'sync_autostart_path']
