"""Qualify one exact committed bundle using isolated files and fake services."""
import argparse
import contextlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT / 'bridge'), str(ROOT / 'tests')]
import runtime_package
import runtime_release as release
import runtime_upgrade as upgrade
from test_runtime_install import FakeHost


def qualify(scratch, evidence, previous_program=None):
    if upgrade.git(ROOT, 'status', '--porcelain').strip():
        raise ValueError('package qualification requires a clean committed checkout')
    revision = upgrade.git(ROOT, 'rev-parse', 'HEAD').decode().strip()
    node, npm = shutil.which('node'), shutil.which('npm')
    if not node or not npm:
        raise ValueError('Node 24 and npm are required')
    scratch.mkdir(mode=0o700, parents=True, exist_ok=True)
    evidence.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='bundle-', dir=scratch) as temporary:
        base = Path(temporary)
        candidate, identity = runtime_package.stage(ROOT, revision, base / 'build', node, npm)
        installation = base / 'installation'
        runtime = installation / 'runtime'
        runtime.mkdir(parents=True)
        for name in release.COMPONENTS:
            shutil.copytree((previous_program or candidate) / name, runtime / name, symlinks=True)
        (runtime / 'node').mkdir()
        (runtime / 'node/marker').write_text('shared Node remains owned by its existing installer')
        (runtime / 'hub-gh30').mkdir()
        (runtime / 'hub-gh30/marker').write_text('other-owner legacy Hub')
        for source, target in (('config-fixture.json', 'config.json'), ('layout-fixture.json', 'layout.json'), ('scene-state-fixture.json', 'scene-state.json')):
            shutil.copy2(ROOT / 'tests/fixtures/linux-state-v4' / source, installation / target)
        with contextlib.closing(sqlite3.connect(installation / 'status.sqlite')) as db, db:
            db.executescript((ROOT / 'tests/fixtures/linux-state-v4/status.sql').read_text())
        compatibility = runtime_package.qualify(runtime, candidate, sys.executable, base / 'compatibility', ROOT / 'tests/fixtures/linux-state-v4/status.sql')
        release.write(evidence / 'compatibility.json', compatibility)
        reverse = runtime_package.qualify(candidate, runtime, sys.executable, base / 'reverse-compatibility', ROOT / 'tests/fixtures/linux-state-v4/status.sql')
        release.write(evidence / 'reverse-compatibility.json', reverse)
        previous = upgrade.selected(installation)[1]
        value = {'installation': str(installation), 'requestedTarget': revision, 'operation': 'upgrade', 'previous': previous,
                 'configuration': upgrade.configuration(installation), 'protected': upgrade.protected(installation), 'planSha256': 'b' * 64}
        receipt = upgrade.transition(value, candidate, identity, evidence / 'compatibility.json', FakeHost(installation, fail_target=True), lambda: None)
        if receipt['outcome'] != 'failed-rolled-back' or upgrade.selected(installation)[1] != previous:
            raise ValueError('packaged recovery failed')
        if json.loads((installation / 'scene-state.json').read_bytes()) != {'newer': 'write'}:
            raise ValueError('packaged recovery lost latest state')
        # The second adoption order has an already-migrated Hub link.
        external = base / 'hub-release'
        (runtime / 'hub-gh30').rename(external)
        (runtime / 'hub-gh30').symlink_to(external, target_is_directory=True)
        value['protected'] = upgrade.protected(installation)
        receipt = upgrade.transition(value, candidate, identity, evidence / 'compatibility.json', FakeHost(installation), lambda: None)
        if receipt['outcome'] != 'succeeded' or upgrade.selected(installation)[1] != identity:
            raise ValueError('packaged upgrade failed')
        if upgrade.protected(installation) != value['protected']:
            raise ValueError('packaged other-owner changed')
        if release.build(candidate / 'bridge/controller_server.py') != {key: identity[key] for key in ('sourceRevision', 'version')}:
            raise ValueError('packaged process metadata failed')
        result = {'sourceRevision': revision, 'identity': identity, 'build': json.loads((base / 'build/build.json').read_bytes()),
                  'recovery': 'failed-rolled-back-latest-state-preserved', 'upgrade': 'succeeded',
                  'adoptionOrders': ['Nanoleaf-before-Hub', 'Nanoleaf-after-Hub'],
                  'previousCode': 'explicit-read-only-program-copy' if previous_program else 'candidate-fixture',
                  'services': 'fake', 'installedAcceptance': False, 'physicalAcceptance': False}
        release.write(evidence / 'package.json', result)
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scratch', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--previous-program', type=Path, help='Read-only previous bridge/MCP/vendor program roots to copy into the isolated fixture.')
    args = parser.parse_args()
    with contextlib.ExitStack() as stack:
        prior = os.umask(0o077)
        stack.callback(os.umask, prior)
        print(json.dumps(qualify(args.scratch.absolute(), args.evidence.absolute(), args.previous_program), indent=2))
