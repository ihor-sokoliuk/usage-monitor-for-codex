"""Entry point for ``python -m usage_monitor_for_claude``."""
from __future__ import annotations

import ctypes
import logging
import os
import subprocess
import sys
import traceback
from pathlib import Path

from usage_monitor_for_claude.dpi import set_process_dpi_awareness
from usage_monitor_for_claude.instance_id import parse_codex_home

_verbose = '--verbose' in sys.argv

# --codex-home selects which Codex account to monitor. It must be
# resolved into CODEX_HOME before any other package import:
# api, settings, verbose and i18n all read the variable at import or
# first-use time. Keep every other package import below this block.
_config_dir = parse_codex_home(sys.argv)
if _config_dir is not None:
    _config_path = Path(_config_dir)
    if not _config_path.is_dir():
        ctypes.windll.user32.MessageBoxW(
            0, f'--codex-home directory does not exist:\n{_config_dir}',
            'Usage Monitor for Codex - Error', 0x10,
        )
        sys.exit(1)
    os.environ['CODEX_HOME'] = str(_config_path.resolve())

# In frozen builds (console=False), stdout/stderr go nowhere.
# --verbose attaches a console so diagnostics are visible.
if _verbose and getattr(sys, 'frozen', False):
    from usage_monitor_for_claude.verbose import setup_console
    setup_console()

# Per-Monitor V2 must be set before pywebview's legacy SetProcessDPIAware() call,
# which only sets SYSTEM_DPI_AWARE and breaks native menu hover at high DPI.
set_process_dpi_awareness()

from usage_monitor_for_claude.logging_setup import configure_logging
from usage_monitor_for_claude.settings import LOG_BACKUP_COUNT, LOG_MAX_BYTES

try:
    _log_path = configure_logging(
        verbose=_verbose,
        max_bytes=LOG_MAX_BYTES,
        backup_count=LOG_BACKUP_COUNT,
    )
except OSError as exc:
    ctypes.windll.user32.MessageBoxW(
        0,
        f'Cannot create the application log next to the executable:\n{exc}',
        'Usage Monitor for Codex - Logging Error',
        0x10,
    )
    sys.exit(1)

_logger = logging.getLogger(__name__)


def _log_diagnostics(callback) -> None:
    """Write verbose-style diagnostic output to the always-on log."""
    from usage_monitor_for_claude.verbose import capture_diagnostics

    for line in capture_diagnostics(callback).splitlines():
        if line.strip():
            _logger.info('diagnostic: %s', line.strip())


from usage_monitor_for_claude.verbose import print_startup_diagnostics
_log_diagnostics(print_startup_diagnostics)

import webview  # type: ignore[import-untyped]  # no type stubs available

from usage_monitor_for_claude.app import UsageMonitorForCodex, crash_log
from usage_monitor_for_claude.single_instance import ensure_single_instance, release_instance_lock

_result: dict = {}


def _verbose_step(label: str) -> None:
    """Log a startup progress step; --verbose mirrors it to the console."""
    _logger.info('startup: %s', label)


def _run_app() -> None:
    """Run the tray application in a background thread (called by webview)."""
    try:
        from usage_monitor_for_claude.verbose import print_runtime_diagnostics
        _log_diagnostics(print_runtime_diagnostics)

        _verbose_step('UsageMonitorForCodex()...')
        app = UsageMonitorForCodex()
        _verbose_step('UsageMonitorForCodex()... OK')

        _verbose_step('app.run...')
        app.run()
        _result['app'] = app
    except Exception:
        _verbose_step(f'CRASH: {traceback.format_exc()}')
        crash_log(traceback.format_exc())
    finally:
        # Destroy all webview windows (keeper + any open popups) so
        # webview.start() on the main thread returns.
        for win in list(webview.windows):
            try:
                win.destroy()
            except Exception:
                pass


try:
    _verbose_step('ensure_single_instance...')
    if not ensure_single_instance():
        _verbose_step('another instance is running, exiting')
        sys.exit(0)
    _verbose_step('ensure_single_instance... OK')

    # pywebview requires the main thread for its GUI event loop.
    # A persistent hidden window keeps the loop alive while the
    # tray app and popup windows are managed in background threads.
    _verbose_step('webview.create_window...')
    webview.create_window('', html='', hidden=True)
    _verbose_step('webview.create_window... OK')

    _verbose_step('webview.start...')
    try:
        webview.start(func=_run_app)
    finally:
        from usage_monitor_for_claude.api import shutdown_transport
        shutdown_transport()
    _verbose_step('webview.start returned')

    app = _result.get('app')
    if app and app.restart_requested:
        release_instance_lock()

        passthrough_args = []
        if _config_dir is not None:
            passthrough_args.append(f'--codex-home={os.environ["CODEX_HOME"]}')
        if _verbose:
            passthrough_args.append('--verbose')

        if getattr(sys, 'frozen', False):
            # Clear PyInstaller's internal env vars so the new
            # instance extracts to a fresh temp directory instead
            # of reusing the current (soon-to-be-deleted) one.
            env = {k: v for k, v in os.environ.items() if not k.startswith(('_PYI_', '_MEI'))}
            subprocess.Popen(
                [sys.executable, *passthrough_args],
                env=env,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        else:
            subprocess.Popen(
                [sys.executable, '-m', 'usage_monitor_for_claude', *passthrough_args],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
except Exception:
    crash_log(traceback.format_exc())
