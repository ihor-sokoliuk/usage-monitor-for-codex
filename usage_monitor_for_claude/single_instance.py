"""Platform-specific application instance compatibility exports."""
from __future__ import annotations

from .platforms.instance import ensure_single_instance, release_instance_lock

__all__ = ['ensure_single_instance', 'release_instance_lock']
