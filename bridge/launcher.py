"""Starts detached bridge.py processes: one light worker per registered device, or the wall map."""
from pathlib import Path
import subprocess
import sys

import configuration

# Every worker and map process runs the CLI entry point beside this module.
SCRIPT = Path(__file__).resolve().with_name('bridge.py')


def start(*arguments):
    """Start bridge.py with arguments in its own session, detached from the caller's streams."""
    return subprocess.Popen([sys.executable, str(SCRIPT), *arguments], stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True,
                            start_new_session=True)


def launch_worker(directory, device=None):
    """Wake one worker instance per registered device, or only the named device."""
    for target in [device] if device else configuration.registered_devices(directory):
        start('worker', '--state-dir', str(directory.resolve()), '--device', target)
