"""
Instance Identity
==================

Derives a per-instance identifier from the effective Codex home
directory so multiple monitor instances (one per Codex account) can
coexist, each guarding its own single-instance mutex and autostart
registry entry.

This module must stay free of imports from ``api`` or ``settings`` -
it is used before ``CODEX_HOME`` is finalized in ``__main__``.
"""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

__all__ = ['config_dir_suffix', 'effective_config_dir', 'is_default_config_dir', 'parse_codex_home']


def parse_codex_home(argv: list[str]) -> str | None:
    """Extract the ``--codex-home`` value from command-line arguments.

    Supports both ``--codex-home=PATH`` and ``--codex-home PATH`` forms.
    Surrounding quotes and a stray trailing quote (left by cmd.exe when
    the path ends with a backslash, e.g. ``--codex-home="C:\\dir\\"``)
    are stripped.  Environment variables (``%USERPROFILE%``) and a
    leading ``~`` are expanded, so the flag works the same from cmd.exe,
    PowerShell, and shortcut targets.

    Parameters
    ----------
    argv : list[str]
        Argument list, typically ``sys.argv``.

    Returns
    -------
    str | None
        The cleaned path value, or ``None`` if the flag is absent or
        has no value.
    """
    value = None
    for index, arg in enumerate(argv):
        if arg.startswith('--codex-home='):
            value = arg.split('=', 1)[1]
        elif arg == '--codex-home' and index + 1 < len(argv):
            value = argv[index + 1]

    if value is None:
        return None

    value = value.strip().strip('"').rstrip('\\/')
    if not value:
        return None

    if re.fullmatch(r'[A-Za-z]:', value):
        value += '\\'

    return str(Path(os.path.expandvars(value)).expanduser())


def effective_config_dir() -> Path:
    """Return the resolved Codex home directory currently in effect."""
    custom = os.environ.get('CODEX_HOME')
    base = Path(custom) if custom else Path.home() / '.codex'
    return base.resolve()


def is_default_config_dir() -> bool:
    """Return True when the effective config dir is the default ``~/.codex``."""
    default = (Path.home() / '.codex').resolve()
    return os.path.normcase(str(effective_config_dir())) == os.path.normcase(str(default))


def config_dir_suffix() -> str:
    """Return a per-instance suffix for kernel object and registry names.

    Empty for the default ``~/.codex`` directory, otherwise an underscore
    plus a short hash of the resolved, case-normalized directory path.
    Hashing keeps the names free of characters that are invalid in Win32
    kernel object names (e.g. backslashes).
    """
    if is_default_config_dir():
        return ''

    normalized = os.path.normcase(str(effective_config_dir()))
    return '_' + hashlib.sha1(normalized.encode('utf-8')).hexdigest()[:12]
