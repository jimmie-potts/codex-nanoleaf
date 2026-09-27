"""`scripts/demo.py` beneath a test backstop (#194): a regression in the boundary cannot reach an installed service.

It runs the demo unchanged, except that right after the demo installs its boundary it adds a second
audit hook. Python calls audit hooks in the order they were added and stops at the first that
raises, so the backstop sees only what the boundary let through. It lets a TCP connect through only
to 127.0.0.1 on the run's paired Hub port and never to an installed service's port. Anything else it
records in `backstop.jsonl` beside the state directory, where a reseed does not remove it, and
refuses. A test that finds any line there has found a boundary regression.
"""
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / 'scripts/demo.py'
spec = importlib.util.spec_from_file_location('demo', DEMO)
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)
BACKSTOP_LOG = 'backstop.jsonl'
installed_boundary = demo.install_boundary


def install_boundary(log, paired_port=None):
    boundary = installed_boundary(log, paired_port)
    record = Path(log).resolve().parent.parent / BACKSTOP_LOG

    def backstop(name, args):
        if name not in ('socket.connect', 'socket.sendto', 'socket.sendmsg'):
            return
        address = args[1] if len(args) > 1 else None
        port = address[1] if isinstance(address, tuple) and len(address) >= 2 else None
        if (name == 'socket.connect' and port not in demo.INSTALLED_PORTS and paired_port is not None
                and address == ('127.0.0.1', paired_port)):
            return
        with open(record, 'a', encoding='utf-8') as stream:
            stream.write(json.dumps({'event': name, 'target': str(address)}) + '\n')
        raise ConnectionRefusedError('The test backstop refused a connection the boundary let through.')
    sys.addaudithook(backstop)
    return boundary


demo.install_boundary = install_boundary
sys.argv[0] = str(DEMO)  # argparse names the program demo.py, so failure lines read as the demo's own.
demo.main(sys.argv[1:])
