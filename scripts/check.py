"""Run the isolated Python regression suite from any working directory."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True

if __name__ == '__main__':
    for source in (ROOT / 'bridge').glob('*.py'):
        compile(source.read_text(encoding='utf-8'), str(source), 'exec')
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'), pattern='test_*.py')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
