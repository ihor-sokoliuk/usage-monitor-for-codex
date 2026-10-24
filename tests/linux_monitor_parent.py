"""Synthetic monitor parent killed by Linux lifecycle integration tests."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from usage_monitor_for_claude.app_server import AppServerTransport


def main() -> None:
    """Keep a supervised synthetic provider alive until the test kills us."""
    state = Path(sys.argv[1])
    child = Path(__file__).with_name('linux_lifecycle_child.py')
    transport = AppServerTransport(command=[sys.executable, str(child), '--state', str(state), '--mode', 'detached'])
    transport.run_operation(lambda operation: operation.request('account/read', {}))
    with state.open('a', encoding='utf-8') as output:
        output.write(json.dumps({'event': 'supervisor', 'pid': transport._proc.pid}) + '\n')
    while True:
        time.sleep(1)


if __name__ == '__main__':
    main()
