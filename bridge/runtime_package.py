"""Build and qualify the complete candidate beside the established installation."""
import ast
import contextlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import tarfile
import time

import runtime_host
import runtime_release as release

BRIDGE_ASSETS = ('wall.html', 'prism.js', 'prism-adapters.js', 'prism-labels.js', 'requirements-controller.txt')
# Qualified diagnostics-only adoption: e15de12 -> 8cc11c4 (#209). These are
# normalized complete product-module hashes, not inferred release identities.
# Both directions still require dependency and target-write/previous-reopen proof.
DIAGNOSTICS_ADOPTION = frozenset({
    'a09cf5451cdd9800fadf5ae8fedc6e17c3dae509a6819b784f6d91f051297b9e',
    '3cf143cfdbdb1e32f6ea8043b8f00b3fbc14b455804d2b71778ffb34fa7f1915',
})


def copy_payload(source, target):
    source, target = Path(source), Path(target)
    (target / 'bridge').mkdir(parents=True)
    for path in (source / 'bridge').glob('*.py'):
        if path.name != 'install_linux.py':
            shutil.copy2(path, target / 'bridge' / path.name)
    for name in BRIDGE_ASSETS:
        shutil.copy2(source / 'bridge' / name, target / 'bridge' / name)
    shutil.copytree(source / 'bridge/vendor', target / 'bridge/vendor', symlinks=True)
    shutil.copytree(source / 'vendor', target / 'vendor', symlinks=True)
    (target / 'mcp').mkdir()
    for name in ('package.json', 'package-lock.json', 'tsconfig.json'):
        shutil.copy2(source / 'mcp' / name, target / 'mcp' / name)
    for name in ('src', 'scripts'):
        shutil.copytree(source / 'mcp' / name, target / 'mcp' / name, symlinks=True)


def stage(source, revision, destination, node, npm, python=None):
    destination, source = Path(destination), Path(source)
    started = time.monotonic()
    archive = runtime_host.run(['git', '-C', source, 'archive', '--format=tar', revision]).stdout
    checkout = destination / 'source'
    checkout.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(archive)) as package:
        package.extractall(checkout, filter='data')
    payload = destination / 'payload'
    copy_payload(checkout, payload)
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PATH=str(Path(node).parent) + os.pathsep + os.environ.get('PATH', ''))
    if not re.fullmatch(r'v24\.\d+\.\d+', runtime_host.run([node, '--version'], text=True).stdout.strip()):
        raise ValueError('shared-node-24-required')
    # Dependency lifecycle scripts are not part of this package's build contract.
    runtime_host.run([npm, 'ci', '--ignore-scripts', '--no-audit', '--no-fund'], cwd=payload / 'mcp', env=environment, timeout=300)
    runtime_host.run([node, 'scripts/verify.mjs'], cwd=payload / 'mcp', env=environment)
    runtime_host.run([node, 'node_modules/typescript/bin/tsc', '-p', 'tsconfig.json'], cwd=payload / 'mcp', env=environment)
    python = python or sys.executable
    # Immutable, target-owned wheels leave the shared interpreter/environment and
    # every retained previous release untouched. No sdist build or install hook.
    pins = requirements(payload / 'bridge/requirements-controller.txt')
    runtime_host.run([python, '-I', '-m', 'pip', 'install', '--only-binary=:all:', '--no-deps',
                      '--no-compile', '--disable-pip-version-check', '--target', payload / 'bridge/python-deps',
                      *(name + '==' + version for name, version in sorted(pins.items()))],
                    env=environment, timeout=300)
    verify_dependencies(payload, python)
    # No Python cache is shipped. Every managed bridge entry disables subsequent writes.
    for path in payload.rglob('__pycache__'):
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
    identity = release.seal(payload, revision, json.loads((checkout / 'package.json').read_bytes())['version'], archive)
    release.verify(payload)
    release.write(destination / 'build.json', {'identity': identity, 'seconds': round(time.monotonic() - started, 3),
                                             'pythonStrategy': 'release-owned-wheels-shared-interpreter', 'npmLifecycleScripts': False})
    return payload, identity


def durable_fingerprint(program):
    """Conservative first qualification, like Hub's durableFingerprint.

    All old product Python modules remain part of the fingerprint. Only this
    updater's new modules and the two read-only build-metadata additions are
    excluded. A future product implementation change requires explicit renewed
    compatibility qualification; matching a version integer is insufficient.
    """
    found = {}
    for path in sorted((Path(program) / 'bridge').glob('*.py')):
        if path.name == 'install_linux.py' or path.name == 'install_contract.py' or path.name.startswith('runtime_'):
            continue
        source = path.read_text()
        if path.name == 'bridge.py':
            source = source.replace('sys.dont_write_bytecode = True\n', '')
            source = source.replace("sys.path.insert(0, str(Path(__file__).resolve().parent / 'python-deps'))\n", '')
        if path.name == 'controller_server.py':
            source = source.replace('import runtime_release\n', '')
            source = source.replace('        self.build=runtime_release.build(__file__)\n', '')
            source = source.replace("                    if parts.path=='/controller/meta/v1/health' and not query:\n                        return self.respond(200,dict(apiVersion='1.0',serviceHealth='ready',build=dict(app.build)))\n", '')
        found[path.name] = release.digest(ast.dump(ast.parse(source), include_attributes=False).encode())
    if 'database.py' not in found or 'bridge.py' not in found:
        raise ValueError('durable-implementation-unavailable')
    return release.digest(release.encoded(found))


def requirements(path, seen=None):
    path = Path(path)
    seen = set() if seen is None else seen
    if path in seen:
        raise ValueError('recursive-python-requirements')
    seen.add(path)
    found = {}
    for raw in path.read_text().splitlines():
        line = raw.split('#', 1)[0].strip()
        if not line:
            continue
        if line.startswith('-r '):
            child = (path.parent / line[3:]).resolve()
            if not child.is_relative_to(path.parent.resolve()):
                raise ValueError('python-requirement-escape')
            found.update(requirements(child, seen))
        else:
            match = re.fullmatch(r'([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+!-]+)', line)
            if not match:
                raise ValueError('unpinned-python-dependency')
            name = re.sub(r'[-_.]+', '-', match[1]).lower()
            if name in found and found[name] != match[2]:
                raise ValueError('conflicting-python-dependency')
            found[name] = match[2]
    return found


DEPENDENCY_PROBE = '''
import importlib.metadata,json,sys
from pathlib import Path
bundle=Path(sys.argv[2])/'python-deps'
if bundle.is_dir():sys.path.insert(0,str(bundle))
expected=json.loads(sys.argv[1])
for name,version in expected.items():
    distribution=importlib.metadata.distribution(name)
    if distribution.version!=version: raise RuntimeError('dependency-version')
    if bundle.is_dir() and not Path(distribution.locate_file('')).resolve().is_relative_to(bundle.resolve()):
        raise RuntimeError('dependency-outside-release')
import jsonschema
print(json.dumps(expected,sort_keys=True))
'''


def verify_dependencies(program, python):
    program = Path(program)
    dependencies = requirements(program / 'bridge/requirements-controller.txt')
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    runtime_host.run([python, '-I', '-c', DEPENDENCY_PROBE, json.dumps(dependencies), program / 'bridge'], env=environment)
    runtime_host.run([python, '-I', '-c',
                     "import sys,runpy;sys.path.insert(0,sys.argv[1]);sys.argv=['pip','check'];runpy.run_module('pip',run_name='__main__')",
                     program / 'bridge/python-deps'], env=environment)
    return dependencies

STATE_PROBE = '''
import contextlib,json,sqlite3,sys
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,sys.argv[1])
sys.path.insert(0,str(Path(sys.argv[1])/'python-deps'))
import database,project_map,shared_input,controller_state,integration_api
directory=Path(sys.argv[2]);mode=sys.argv[3]
with contextlib.closing(database.connect_state(directory)) as db,db:
    if mode=='write':
        project='upgrade-probe-project'; task='upgrade-probe-task'
        database.seed_synthetic(db,[{'id':project,'name':'Probe','color':'#123456'}],
            [{'id':task,'title':'Probe','project':project,'status':'unread','since':1234.0}])
        db.execute('INSERT INTO receipts VALUES (?,?,?,?)',(task,'1',1234.0,0))
    project_map.settings(db);project_map.palette(db);project_map.task_projects(db)
    shared_input.state(db);shared_input.dump_tables(db);integration_api.favorites(db)
    for device in controller_state.ledgers(db):
        controller_state.read(db,device);controller_state.snapshot(db,device)
    if db.execute('PRAGMA integrity_check').fetchone()!=('ok',): raise RuntimeError('integrity')
    dump=list(db.iterdump())
print(json.dumps(dump))
'''


def qualify(previous, target, python, scratch, fixture):
    previous, target, scratch = Path(previous), Path(target), Path(scratch)
    previous_fingerprint, target_fingerprint = durable_fingerprint(previous), durable_fingerprint(target)
    if previous_fingerprint != target_fingerprint and frozenset((previous_fingerprint, target_fingerprint)) != DIAGNOSTICS_ADOPTION:
        raise ValueError('durable-implementation-unqualified')
    dependencies = verify_dependencies(target, python)
    prior = verify_dependencies(previous, python)
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    scratch.mkdir(parents=True)
    with contextlib.closing(sqlite3.connect(scratch / 'status.sqlite')) as db, db:
        db.executescript(Path(fixture).read_text())
    def probe(program, mode):
        return json.loads(runtime_host.run([python, '-I', '-c', STATE_PROBE, program / 'bridge', scratch, mode], env=environment).stdout)
    written = probe(target, 'write')
    reopened = probe(previous, 'reopen')
    if reopened != written:
        raise ValueError('previous-code-changed-latest-state')
    return {'status': 'compatible', 'durableFingerprint': target_fingerprint, 'previousDurableFingerprint': previous_fingerprint,
            'dependencies': dependencies, 'previousDependencies': prior, 'stateSha256': release.digest(release.encoded(written)),
            'probe': 'target-write-previous-reopen', 'latestStateRestoredFromBackup': False}


def reopen_current(previous, target, python, snapshot):
    """Both programs reopen a private consistent copy; changes are unqualified."""
    snapshot = Path(snapshot)
    with contextlib.closing(sqlite3.connect(snapshot / 'status.sqlite')) as db:
        before = list(db.iterdump())
    files = {path.name: release.digest(path.read_bytes()) for path in snapshot.iterdir() if path.suffix == '.json'}
    for program in (target, previous):
        result = runtime_host.run([python, '-I', '-c', STATE_PROBE, Path(program) / 'bridge', snapshot, 'reopen'],
                                  env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        if json.loads(result.stdout) != before:
            raise ValueError('installed-state-migration-unqualified')
        if files != {path.name: release.digest(path.read_bytes()) for path in snapshot.iterdir() if path.suffix == '.json'}:
            raise ValueError('installed-configuration-migration-unqualified')
    return release.digest(release.encoded(before))
