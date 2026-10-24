"""Synthetic Linux child trees for process lifecycle regression tests."""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def record(path: Path, event: str) -> None:
    """Append a synthetic lifecycle event to the test-owned file."""
    with path.open('a', encoding='utf-8') as output:
        output.write(json.dumps({'event': event, 'pid': os.getpid()}) + '\n')


def main() -> int:
    """Run a scripted child or a detached, stubborn descendant."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--mode', default='normal')
    parser.add_argument('--descendant', action='store_true')
    arguments = parser.parse_args()
    if arguments.descendant:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        record(arguments.state, 'descendant')
        while True:
            time.sleep(1)

    record(arguments.state, 'child')
    if arguments.mode in ('tree', 'detached', 'crash'):
        subprocess.Popen(
            [sys.executable, __file__, '--state', str(arguments.state), '--descendant'],
            start_new_session=arguments.mode == 'detached',
        )
    if arguments.mode == 'bad-handshake':
        print('invalid synthetic protocol', flush=True)
        time.sleep(30)
        return 1
    for line in sys.stdin:
        message = json.loads(line)
        if message.get('method') == 'initialized':
            record(arguments.state, 'ready')
            if arguments.mode == 'blocked':
                while True:
                    time.sleep(1)
            continue
        if 'id' not in message:
            continue
        print(json.dumps({'id': message['id'], 'result': {'ok': True}}), flush=True)
        if message.get('method') != 'initialize' and arguments.mode == 'crash':
            return 1
    record(arguments.state, 'eof')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
