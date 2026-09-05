"""Take a consistent copy of bridge state before a Windows upgrade."""
import contextlib
from pathlib import Path
import shutil
import sqlite3
import sys


def backup(source, destination):
    for name in ('status.sqlite',):
        if (source / name).exists():
            with contextlib.closing(sqlite3.connect(source / name, timeout=10)) as original:
                with contextlib.closing(sqlite3.connect(destination / name)) as copy:
                    original.backup(copy)
    for name in ('config.json', 'layout.json', 'scene-state.json'):
        if (source / name).exists():
            shutil.copyfile(source / name, destination / name)


if __name__ == '__main__':
    backup(Path(sys.argv[1]), Path(sys.argv[2]))
