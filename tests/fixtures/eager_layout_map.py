"""A wall map that reads its layout on every poll: the defect the bounded layout-read checks must catch (#193).

It runs `scripts/demo.py` unchanged, except that each state read resets the map's layout retry
bound, as a regression that polled an unreachable device would.
"""
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('demo', ROOT / 'scripts/demo.py')
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)
import wall_server  # noqa: E402  (demo put bridge/ on the import path)

bounded_state = wall_server.App.state


def eager_state(self, device=None):
    self.geometry_attempts = 0
    self.geometry_retry = 0
    return bounded_state(self, device)


wall_server.App.state = eager_state
demo.main(sys.argv[1:])
