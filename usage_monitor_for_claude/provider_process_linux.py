"""Launch the Linux provider supervisor with a parent-owned liveness pipe."""
from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path

__all__ = ['ControlPipe', 'spawn_supervised']


class ControlPipe:
    """Own the only write end of one supervisor's parent-liveness pipe."""

    def __init__(self, descriptor: int) -> None:
        self._descriptor: int | None = descriptor
        self._lock = threading.Lock()

    def close(self) -> None:
        """Request bounded descendant cleanup by delivering control EOF."""
        with self._lock:
            descriptor = self._descriptor
            self._descriptor = None
        if descriptor is not None:
            os.close(descriptor)


def spawn_supervised(command: list[str], environment: dict[str, str]) -> tuple[subprocess.Popen, ControlPipe]:
    """Start an isolated supervisor whose child inherits protocol stdio directly.

    Parameters
    ----------
    command : list[str]
        Fixed provider command selected by the transport.
    environment : dict[str, str]
        Child environment, including an optional caller-selected Codex home.

    Returns
    -------
    tuple[subprocess.Popen, ControlPipe]
        The supervisor process and its monitor-owned liveness pipe.
    """
    read_descriptor, write_descriptor = os.pipe()
    control = ControlPipe(write_descriptor)
    supervisor = Path(__file__).with_name('_linux_supervisor.py')
    try:
        process = subprocess.Popen(
            [sys.executable, str(supervisor), str(read_descriptor), *command],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding='utf-8', errors='replace', env=environment,
            close_fds=True, pass_fds=(read_descriptor,), start_new_session=True,
        )
    except BaseException:
        control.close()
        raise
    finally:
        os.close(read_descriptor)
    return process, control
