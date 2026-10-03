"""Exact-plan Nanoleaf transitions. Filesystem ownership is limited to this installation."""
import argparse
import contextlib
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import uuid

import install_contract
import runtime_host
import runtime_package
import runtime_release as release

REMOTE = 'https://github.com/jimmie-potts/codex-nanoleaf.git'
PRIVATE_CONFIG = ('config.json', 'layout.json', 'controller.json', 'mcp-config.json',
                  'mcp-credentials.json', 'mcp-client-token')
MANAGED = {'runtime', '.venv', 'releases', 'legacy', 'receipts', 'upgrade-records',
           'upgrade-backups', 'upgrade-staging', 'current'}


def private_directory(path):
    path = Path(path)
    if path.is_symlink() or path.resolve() != path.absolute():
        raise ValueError('owned-directory-link')
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.stat().st_uid != os.getuid():
        raise ValueError('foreign-owned-directory')
    return path


def file_fact(path):
    path = Path(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError('configuration-not-owned-file')
    return {'sha256': release.digest(path.read_bytes()), 'mode': stat.S_IMODE(info.st_mode),
            'uid': info.st_uid, 'inode': info.st_ino}


def configuration(directory):
    directory = Path(directory)
    result = {name: file_fact(directory / name) for name in PRIVATE_CONFIG if (directory / name).exists()}
    database = directory / 'status.sqlite'
    if database.exists():
        with contextlib.closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as db:
            tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if 'controller_credentials' in tables:
                result['controller-credentials'] = {'sha256': release.digest(release.encoded(list(db.execute('SELECT * FROM controller_credentials ORDER BY principal'))))}
            identities = {}
            for name in sorted(tables):
                if name == 'controller_meta' or re.fullmatch(r'controller_meta@[A-Za-z0-9_.-]+', name):
                    row = db.execute('SELECT payload FROM "' + name + '" WHERE id=1').fetchone()
                    if row:
                        identities[name] = json.loads(row[0])['identity']
            if identities:
                result['controller-identities'] = {'sha256': release.digest(release.encoded(identities))}
    return result


def protected(directory):
    """Record excluded roots without moving, following for deletion, or copying them."""
    directory = Path(directory)
    result = {}
    for name in ('runtime/node', 'runtime/hub-gh30', '.venv'):
        path = directory / name
        if not path.exists():
            result[name] = None
            continue
        entries = {}
        root = path.resolve()
        for item in [root, *sorted(root.rglob('*'))]:
            relative = '.' if item == root else item.relative_to(root).as_posix()
            info = item.lstat()
            entry = {'mode': stat.S_IMODE(info.st_mode), 'inode': info.st_ino}
            if item.is_symlink():
                entry.update(link=os.readlink(item), resolved=str(item.resolve()))
                if item.resolve().is_file():
                    entry['sha256'] = release.digest(item.resolve().read_bytes())
            elif item.is_file():
                entry['sha256'] = release.digest(item.read_bytes())
            elif not item.is_dir():
                raise ValueError('unsupported-protected-entry')
            entries[relative] = entry
        result[name] = {'link': os.readlink(path) if path.is_symlink() else None,
                        'resolved': str(root), 'entriesSha256': release.digest(release.encoded(entries))}
    return result


def legacy_identity(root):
    files = release.payload(root)
    content = release.digest(release.encoded(files))
    manifest = {'format': 1, 'kind': 'legacy', 'files': files}
    return dict(kind='legacy', legacyId='legacy-' + content[:16], sourceRevision='unknown',
                contentSha256=content, manifestSha256=release.digest(release.encoded(manifest)))


def verify_bundle(path, identity):
    observed = release.verify(path) if identity['kind'] == 'release' else legacy_identity(path)
    if observed != identity:
        raise ValueError('bundle-identity-drift')
    return observed


def rollback_target(directory, requested):
    if requested != 'previous':
        path = Path(directory) / 'releases' / requested
        if not release.SHA.fullmatch(requested):
            raise ValueError('rollback-full-sha-required')
        return path, release.verify(path)
    marker = Path(directory) / 'upgrade-records/latest-success.json'
    if not marker.is_file() or marker.is_symlink():
        raise ValueError('no-successful-recovery-target')
    operation = json.loads(marker.read_bytes())['operationId']
    if not re.fullmatch(r'nanoleaf-[0-9a-f]{32}', operation):
        raise ValueError('invalid-success-marker')
    receipt_path = Path(directory) / 'receipts' / (operation + '.json')
    if receipt_path.is_symlink():
        raise ValueError('receipt-link')
    value = json.loads(receipt_path.read_bytes())
    if not install_contract.validate_receipt(value) or value['operationId'] != operation or value['outcome'] != 'succeeded' or value['runtime'] != 'nanoleaf':
        raise ValueError('invalid-success-marker')
    previous = value['previous']
    name = previous['sourceRevision'] if previous['kind'] == 'release' else previous['legacyId']
    path = Path(directory) / ('releases' if previous['kind'] == 'release' else 'legacy') / name
    return path, verify_bundle(path, previous)


def selected(directory):
    directory = Path(directory)
    runtime = directory / 'runtime'
    if runtime.is_symlink() or not runtime.is_dir():
        raise ValueError('runtime-parent-must-remain-directory')
    if set(p.name for p in runtime.iterdir()) - {*release.COMPONENTS, 'node', 'hub-gh30'}:
        raise ValueError('unknown-runtime-ownership')
    current = directory / 'current'
    if current.is_symlink():
        target = current.resolve(strict=True)
        if target.parent not in (directory / 'releases', directory / 'legacy'):
            raise ValueError('current-outside-owned-releases')
        if any(not (runtime / name).is_symlink() or os.readlink(runtime / name) != '../current/' + name for name in release.COMPONENTS):
            raise ValueError('partial-component-adoption')
        identity = release.verify(target) if target.parent.name == 'releases' else legacy_identity(target)
        if target.name != identity.get('sourceRevision') and target.name != identity.get('legacyId'):
            raise ValueError('selected-directory-identity')
        return target, identity
    if current.exists() or any((runtime / name).is_symlink() for name in release.COMPONENTS):
        raise ValueError('partial-component-adoption')
    return runtime, legacy_identity(runtime)


def git(source, *arguments):
    return runtime_host.run(['git', '-C', source, *arguments]).stdout


def source_identity(source, requested):
    source = Path(source).resolve()
    if git(source, 'status', '--porcelain').strip():
        raise ValueError('dirty-installer-source')
    remote = git(source, 'remote', 'get-url', 'origin').decode().strip()
    if remote not in (REMOTE, REMOTE.removesuffix('.git'), 'git@github.com:jimmie-potts/codex-nanoleaf.git'):
        raise ValueError('untrusted-source-remote')
    main = git(source, 'ls-remote', '--exit-code', 'origin', 'refs/heads/main').decode().split()[0]
    if not release.SHA.fullmatch(main):
        raise ValueError('unknown-merged-main')
    target = main if requested == 'main' else requested
    if not release.SHA.fullmatch(target):
        raise ValueError('full-merged-sha-required')
    git(source, 'merge-base', '--is-ancestor', target, main)
    return target, main


def unresolved(directory):
    if (Path(directory) / 'upgrade-records/active.json').exists():
        raise ValueError('unresolved-operation-inspection-required')
    records = Path(directory) / 'receipts'
    if records.is_symlink():
        raise ValueError('receipt-directory-link')
    for path in sorted(records.glob('nanoleaf-*.json')):
        if not re.fullmatch(r'nanoleaf-[0-9a-f]{32}\.json', path.name):
            continue  # Historical/manual records are retained, never reinterpreted.
        if path.is_symlink():
            raise ValueError('receipt-link')
        receipt = json.loads(path.read_bytes())
        if not install_contract.validate_receipt(receipt) or receipt['runtime'] != 'nanoleaf' or receipt['operationId'] + '.json' != path.name:
            raise ValueError('invalid-existing-receipt')
        if receipt['outcome'] in ('in-progress', 'interrupted', 'rollback-failed', 'receipt-finalization-failed', 'failed-before-switch'):
            raise ValueError('unresolved-operation-inspection-required')


def plan(directory, source, units, requested='main', operation='upgrade', host=None):
    directory, source, units = (Path(p).expanduser().absolute() for p in (directory, source, units))
    if directory.is_symlink() or directory.stat().st_uid != os.getuid() or str(directory).startswith('/mnt/'):
        raise ValueError('unsupported-installation-owner-or-filesystem')
    unresolved(directory)
    current, previous = selected(directory)
    host = host or runtime_host.Host(directory, units)
    roots = [directory / 'runtime' / part for part in ('bridge', 'mcp')]
    roots += [current / part for part in ('bridge', 'mcp')]
    host.qualify(roots)
    services = host.snapshot()
    if operation == 'rollback':
        target_path, target_identity = rollback_target(directory, requested)
        target = target_path.name
        _, main = source_identity(source, 'main')
        archive_sha = target_identity.get('archiveSha256')
    else:
        target, main = source_identity(source, requested)
        archive_sha = release.digest(git(source, 'archive', '--format=tar', target))
    commits = None
    if previous['kind'] == 'release' and release.SHA.fullmatch(target):
        commits = git(source, 'rev-list', '--reverse', previous['sourceRevision'] + '..' + target).decode().splitlines()
    changes = None if commits is None else git(source, 'diff', '--name-only', previous['sourceRevision'], target).decode().splitlines()
    if any(path.is_dir() and path.name not in MANAGED for path in directory.iterdir()):
        raise ValueError('unknown-state-directory-backup-scope')
    value = {'format': 1, 'installation': str(directory), 'source': str(source), 'unitsDirectory': str(units),
             'requestedTarget': requested, 'targetRevision': target, 'mergedMain': main, 'operation': operation,
             'archiveSha256': archive_sha,
             'previous': previous, 'selected': str(current), 'configuration': configuration(directory),
             'protected': protected(directory), 'services': {name: {key: item[key] for key in ('sha256', 'argv', 'active')} for name, item in services.items()},
             'running': {name: item['process'] if item['active'] == 'active' else None for name, item in services.items()},
             'runningBuild': host.running_build(services),
             'commits': commits, 'pullRequests': None, 'changedPaths': changes,
             'outage': 'All three Nanoleaf units and detached bridge workers; bounded stop and health checks.',
             'backupScope': 'All root regular state/configuration files; consistent status.sqlite; excludes worker locks and transient journals.',
             'recovery': 'Verified previous complete code reopens latest durable state. No automatic database restore.',
             'compatibility': 'Must pass isolated target-write/previous-reopen and unchanged shared Python dependency qualification before stop.',
             'admission': 'Temporarily deny traversal of owned bridge/MCP directories, drain supported argv entrypoints, then acquire per-device SQLite locks.',
             'authority': 'Owner standing installation authority applies only to the established target and named routine procedure.'}
    value['planSha256'] = release.digest(release.encoded(value))
    return value


def binding(value):
    # PIDs and process ages naturally change; executable/unit/configuration/bundle identity may not.
    return {key: item for key, item in value.items() if key not in ('running', 'runningBuild', 'planSha256')}


class Fence:
    """Persist exact restoration evidence before kernel-enforced entry exclusion.

    FDs retain inode identity across first-adoption renames. Never restore a
    replacement inode at the old pathname. Interruption leaves the durable record.
    """
    def __init__(self, paths, record):
        self.paths = list(dict.fromkeys(Path(path).resolve() for path in paths))
        self.record = Path(record)
        self.opened = []

    def __enter__(self):
        try:
            facts = []
            for path in self.paths:
                fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                info = os.fstat(fd)
                if info.st_uid != os.getuid():
                    os.close(fd)
                    raise ValueError('foreign-program-directory')
                self.opened.append((fd, stat.S_IMODE(info.st_mode)))
                facts.append({'path': str(path), 'inode': info.st_ino, 'device': info.st_dev,
                              'mode': stat.S_IMODE(info.st_mode),
                              'inventorySha256': release.digest(release.encoded(release.inventory(path)))})
            release.write(self.record, facts)
            for fd, mode in self.opened:
                # Rename across parents needs owner write on the directory;
                # removing every search bit still prevents entrypoint opens.
                os.fchmod(fd, (mode & ~0o111) | 0o200)
                os.fsync(fd)
            return self
        except BaseException:
            self.restore()
            raise

    def restore(self):
        try:
            for fd, mode in self.opened:
                os.fchmod(fd, mode)
                os.fsync(fd)
        finally:
            for fd, _ in self.opened:
                os.close(fd)
            self.opened = []

    def __exit__(self, *_):
        self.restore()


def adopt(directory, legacy, checkpoint=lambda _: None):
    directory, legacy = Path(directory), Path(legacy)
    for index, name in enumerate(release.COMPONENTS, 1):
        original = directory / 'runtime' / name
        os.rename(original, legacy / name)
        release.sync(legacy)
        release.sync(original.parent)
        original.symlink_to('../current/' + name, target_is_directory=True)
        release.sync(original.parent)
        checkpoint(index)


def switch(directory, target):
    directory, target = Path(directory), Path(target)
    temporary = directory / ('.current-' + uuid.uuid4().hex)
    temporary.symlink_to(target.relative_to(directory), target_is_directory=True)
    try:
        os.replace(temporary, directory / 'current')
        release.sync(directory)
    finally:
        temporary.unlink(missing_ok=True)


def state_files(directory):
    result = []
    for path in sorted(Path(directory).iterdir()):
        if path.name in MANAGED or path.name in ('upgrade.lock', 'map-server.json', 'controller-server.json') or path.name.startswith('.current-'):
            continue
        if path.name.startswith('notification-lock') or path.name.endswith(('-wal', '-shm', '-journal')):
            continue
        if path.is_symlink() or not path.is_file():
            raise ValueError('unsupported-state-backup-entry')
        result.append(path)
    return result


def copy_state(directory, destination):
    destination = private_directory(destination)
    for path in state_files(directory):
        if path.name == 'status.sqlite':
            with contextlib.closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as source:
                with contextlib.closing(sqlite3.connect(destination / path.name)) as target:
                    source.backup(target)
        else:
            shutil.copy2(path, destination / path.name)
        with (destination / path.name).open('rb') as output:
            os.fsync(output.fileno())
    release.sync(destination)
    return release.digest(release.encoded(release.inventory(destination)))


def logical_state(directory):
    path = Path(directory) / 'status.sqlite'
    with contextlib.closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
        if db.execute('PRAGMA integrity_check').fetchone() != ('ok',):
            raise ValueError('state-integrity')
        return list(db.iterdump())


def timestamp():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def safe_code(error):
    allowed = {'dirty-installer-source', 'untrusted-source-remote', 'unknown-merged-main', 'full-merged-sha-required',
               'durable-implementation-unqualified', 'durable-implementation-unavailable', 'shared-python-dependency-conflict',
               'installed-state-migration-unqualified', 'installed-configuration-migration-unqualified',
               'previous-code-changed-latest-state', 'plan-document-changed', 'plan-inputs-changed-replan-required',
               'plan-operation-or-installation-mismatch', 'plan-target-mismatch', 'upgrade-full-sha-required',
               'exact-plan-required', 'unresolved-operation-inspection-required', 'partial-component-adoption',
               'routine-upgrade-requires-three-established-active-units', 'unsupported-service-ownership',
               'unsupported-service-command', 'unsupported-service-effects', 'installer-permission-bypass',
               'privileged-service-cannot-be-fenced', 'privileged-runtime-executable', 'privileged-or-foreign-owned-writer',
               'owned-process-entrypoint-unreadable', 'unknown-runtime-ownership', 'unknown-state-directory-backup-scope',
               'writer-stop-timeout', 'service-stop-unverified', 'bounded-health-failure', 'controller-build-mismatch',
               'wall-served-artifact', 'mcp-initialize', 'mcp-session', 'mcp-discovery', 'configuration-drift-during-drain',
               'bundle-identity-drift', 'release-inventory-or-provenance', 'no-successful-recovery-target',
               'post-switch-inventory-drift', 'legacy-preservation-mismatch', 'recovery-inventory-drift', 'plan-drift'}
    if type(error) is ValueError and str(error) in allowed:
        return str(error)
    if isinstance(error, subprocess.SubprocessError):
        return 'bounded-subprocess-failed'
    if isinstance(error, sqlite3.Error):
        return 'sqlite-qualification-failed'
    return 'qualification-or-operation-failed'


def new_receipt(value, previous, target, compatibility, operation_id):
    now = timestamp()
    return {'schemaVersion': 'install-receipt/1.0', 'operationId': operation_id,
            'operation': 'migrate' if previous['kind'] == 'legacy' and not (Path(value['installation']) / 'current').is_symlink() else value['operation'],
            'runtime': 'nanoleaf', 'installationId': 'primary', 'startedAt': now, 'updatedAt': now, 'completedAt': None,
            'requestedTarget': value['requestedTarget'], 'previous': previous, 'target': target,
            'approval': {'planSha256': value['planSha256'], 'baselineSha256': release.digest(release.encoded(previous)),
                         'configurationSha256': release.digest(release.encoded(value['configuration']))},
            'compatibility': {'status': 'compatible', 'evidence': str(compatibility)}, 'backup': None, 'running': None,
            'health': {'status': 'not-checked', 'evidence': None}, 'failure': None,
            'rollback': {'status': 'not-attempted', 'evidence': None},
            'statePreservation': {'strategy': 'latest-durable-state', 'evidence': None}, 'outcome': 'in-progress'}


def persist(path, receipt):
    if receipt['outcome'] == 'in-progress':
        receipt['updatedAt'] = timestamp()
    if not install_contract.validate_receipt(receipt):
        raise ValueError('invalid-generated-receipt')
    release.write(path, receipt)
    if json.loads(Path(path).read_bytes()) != receipt:
        raise ValueError('receipt-readback')


class FinalizationFailure(ValueError):
    def __init__(self, receipt):
        super().__init__('receipt-finalization-failed-inspection-required')
        self.receipt = receipt


def finish(path, receipt, writer=persist):
    receipt['updatedAt'] = timestamp()
    receipt['completedAt'] = None if receipt['outcome'] == 'interrupted' else receipt['updatedAt']
    try:
        writer(path, receipt)
    except Exception as error:
        diagnostic = dict(receipt, outcome='receipt-finalization-failed', completedAt=None,
                          failure={'phase': 'receipt-finalization', 'code': 'durable-write-failed', 'evidence': str(path)})
        if not install_contract.validate_receipt(diagnostic):
            raise ValueError('invalid-finalization-diagnostic') from error
        raise FinalizationFailure(diagnostic) from error


def prune(directory):
    directory = Path(directory)
    current = (directory / 'current').resolve()
    successes = []
    for path in (directory / 'receipts').glob('nanoleaf-*.json'):
        if not re.fullmatch(r'nanoleaf-[0-9a-f]{32}\.json', path.name) or path.is_symlink():
            continue
        receipt = json.loads(path.read_bytes())
        if install_contract.validate_receipt(receipt) and receipt['outcome'] == 'succeeded' and receipt['target']['kind'] == 'release':
            successes.append((path.stat().st_mtime_ns, receipt['operationId'], receipt['target']))
    ordered = []
    for _, _, identity in sorted(successes, reverse=True):
        if identity not in ordered:
            ordered.append(identity)
    prior = [value for value in ordered if value['sourceRevision'] != current.name]
    keep = {current.name, *(value['sourceRevision'] for value in prior[:3])}
    for identity in prior[3:]:
        path = directory / 'releases' / identity['sourceRevision']
        if path.name not in keep and path.exists() and not path.is_symlink() and release.verify(path) == identity:
            shutil.rmtree(path)
    release.sync(directory / 'releases')


def transition(value, candidate, identity, compatibility, host, recheck, final_writer=persist, checkpoint=lambda _: None):
    """The single-writer boundary. Tests inject services, never weaken file guards."""
    directory, candidate = Path(value['installation']), Path(candidate)
    lock = directory / 'upgrade.lock'
    descriptor = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        lock_info = os.fstat(descriptor)
        if not stat.S_ISREG(lock_info.st_mode) or lock_info.st_uid != os.getuid() or lock_info.st_nlink != 1:
            raise ValueError('unsupported-install-lock')
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        unresolved(directory)
        recheck()
        previous_path, previous = selected(directory)
        if previous != value['previous'] or configuration(directory) != value['configuration'] or protected(directory) != value['protected']:
            raise ValueError('plan-drift')
        verify_bundle(candidate, identity)
        operation_id = 'nanoleaf-' + uuid.uuid4().hex
        records = private_directory(directory / 'upgrade-records' / operation_id)
        private_directory(directory / 'receipts')
        private_directory(directory / 'releases')
        private_directory(directory / 'legacy')
        target = directory / ('releases' if identity['kind'] == 'release' else 'legacy') / identity.get('legacyId', identity['sourceRevision'])
        if target.exists():
            verify_bundle(target, identity)
        else:
            shutil.copytree(candidate, target, symlinks=True)
            verify_bundle(target, identity)
            release.sync_tree(target)
            release.sync(target.parent)
        receipt_path = directory / 'receipts' / (operation_id + '.json')
        receipt = new_receipt(value, previous, identity, compatibility, operation_id)
        legacy_adoption = not (directory / 'current').is_symlink()
        recovery_path = directory / 'legacy' / previous['legacyId'] if legacy_adoption else previous_path
        if legacy_adoption and recovery_path.exists():
            raise ValueError('existing-legacy-recovery-conflict')
        active = directory / 'upgrade-records/active.json'
        release.write(active, {'operationId': operation_id, 'receipt': str(receipt_path),
                               'planSha256': value['planSha256'], 'recovery': 'Inspect link, fence records, processes and latest state before resolving this barrier.'})
        persist(receipt_path, receipt)
        phase, switched, converting = 'stop', False, False
        roots = [directory / 'runtime' / name for name in ('bridge', 'mcp')]
        roots += [previous_path / name for name in ('bridge', 'mcp')]
        try:
            with Fence([previous_path / name for name in ('bridge', 'mcp')] + [target / name for name in ('bridge', 'mcp')], records / 'fence.json'):
                host.stop(roots)
                with host.worker_locks():
                    phase = 'backup'
                    if configuration(directory) != value['configuration'] or protected(directory) != value['protected']:
                        raise ValueError('configuration-drift-during-drain')
                    backup = private_directory(directory / 'upgrade-backups' / operation_id)
                    backup_hash = copy_state(directory, backup)
                    receipt['backup'] = {'reference': str(backup), 'sha256': backup_hash}
                    persist(receipt_path, receipt)
                    phase = 'switch'
                    if legacy_adoption:
                        private_directory(recovery_path)
                        converting = True
                        adopt(directory, recovery_path, checkpoint)
                        converting = False
                    switch(directory, target)
                    switched = True
                    checkpoint('switched')
            if legacy_adoption and legacy_identity(recovery_path) != previous:
                raise ValueError('legacy-preservation-mismatch')
            before_start = runtime_host.ticks()
            phase = 'start'
            host.start()
            phase = 'health'
            evidence = host.health(identity, target, before_start)
            if verify_bundle(target, identity) != identity or protected(directory) != value['protected']:
                raise ValueError('post-switch-inventory-drift')
            release.write(records / 'health.json', evidence)
            release.write(records / 'state.json', {'strategy': 'latest-durable-state', 'restoredBackup': False,
                                                  'logicalSha256': release.digest(release.encoded(logical_state(directory)))})
            receipt.update(outcome='succeeded', running={'identity': identity, 'verification': 'build-health' if identity['kind'] == 'release' else 'legacy-process-artifacts', 'evidence': str(records / 'health.json')},
                           health={'status': 'healthy', 'evidence': str(records / 'health.json')},
                           statePreservation={'strategy': 'latest-durable-state', 'evidence': str(records / 'state.json')})
        except Exception as error:
            release.write(records / 'failure.json', {'phase': phase, 'code': safe_code(error)})
            receipt['failure'] = {'phase': phase, 'code': 'operation-' + phase + '-failed', 'evidence': str(records)}
            if converting:
                receipt['outcome'] = 'interrupted'
                receipt['failure'] = {'phase': 'recovery', 'code': 'partial-adoption-inspection-required', 'evidence': str(records)}
            elif not switched:
                # A failed switch may have published before parent fsync failed.
                if (directory / 'current').is_symlink() and (directory / 'current').resolve() == target:
                    receipt['outcome'] = 'interrupted'
                    receipt['failure'] = {'phase': 'recovery', 'code': 'switch-durability-unknown', 'evidence': str(records)}
                else:
                    receipt['outcome'] = 'failed-before-switch'
            else:
                try:
                    recovery_roots = roots + [target / name for name in ('bridge', 'mcp')]
                    with Fence([target / name for name in ('bridge', 'mcp')] + [recovery_path / name for name in ('bridge', 'mcp')], records / 'recovery-fence.json'):
                        host.stop(recovery_roots)
                        with host.worker_locks():
                            latest = logical_state(directory)
                            switch(directory, recovery_path)
                            if latest != logical_state(directory):
                                raise ValueError('rollback-replaced-latest-state')
                    before_start = runtime_host.ticks()
                    host.start()
                    evidence = host.health(previous, recovery_path, before_start)
                    observed = release.verify(recovery_path) if previous['kind'] == 'release' else legacy_identity(recovery_path)
                    if observed != previous or protected(directory) != value['protected']:
                        raise ValueError('recovery-inventory-drift')
                    release.write(records / 'recovery.json', evidence)
                    release.write(records / 'state.json', {'strategy': 'latest-durable-state', 'restoredBackup': False,
                                                          'beforeRestartSha256': release.digest(release.encoded(latest)),
                                                          'afterRestartSha256': release.digest(release.encoded(logical_state(directory)))})
                    receipt.update(outcome='failed-rolled-back', rollback={'status': 'succeeded', 'evidence': str(records / 'recovery.json')},
                                   health={'status': 'healthy', 'evidence': str(records / 'recovery.json')},
                                   running={'identity': previous, 'verification': 'build-health' if previous['kind'] == 'release' else 'legacy-process-artifacts', 'evidence': str(records / 'recovery.json')},
                                   statePreservation={'strategy': 'latest-durable-state', 'evidence': str(records / 'state.json')})
                except Exception:
                    receipt.update(outcome='rollback-failed', rollback={'status': 'failed', 'evidence': str(records)},
                                   failure={'phase': 'rollback', 'code': 'recovery-unverified', 'evidence': str(records)},
                                   health={'status': 'unknown', 'evidence': str(records)})
        def finalize(path, document):
            final_writer(path, document)
            if document['outcome'] == 'succeeded':
                release.write(directory / 'upgrade-records/latest-success.json', {'operationId': operation_id})
        finish(receipt_path, receipt, finalize)
        if receipt['outcome'] in ('succeeded', 'failed-rolled-back'):
            active.unlink()
            release.sync(active.parent)
        if receipt['outcome'] == 'succeeded':
            try:
                prune(directory)
            except (OSError, ValueError):
                # Installed acceptance is already durable. Retain extra history
                # rather than turn a retention failure into a false refusal.
                release.write(records / 'retention.json', {'status': 'inspection-required', 'code': 'retention-incomplete'})
        return receipt
    finally:
        os.close(descriptor)


def check_plan(value):
    content = {key: item for key, item in value.items() if key != 'planSha256'}
    if value.get('planSha256') != release.digest(release.encoded(content)):
        raise ValueError('plan-document-changed')
    fresh = plan(value['installation'], value['source'], value['unitsDirectory'], value['requestedTarget'], value['operation'])
    if binding(fresh) != binding(value):
        raise ValueError('plan-inputs-changed-replan-required')
    if any(item['active'] != 'active' for item in value['services'].values()):
        raise ValueError('routine-upgrade-requires-three-established-active-units')


def operate(value, npm='npm'):
    check_plan(value)
    directory = Path(value['installation'])
    current, _ = selected(directory)
    staging = private_directory(directory / 'upgrade-staging' / uuid.uuid4().hex)
    records = private_directory(directory / 'upgrade-records' / ('qualification-' + uuid.uuid4().hex))
    prior_umask = os.umask(0o077)
    try:
        if value['operation'] == 'rollback':
            target, identity = rollback_target(directory, value['requestedTarget'])
        else:
            target, identity = runtime_package.stage(value['source'], value['targetRevision'], staging,
                                                     directory / 'runtime/node/bin/node', npm)
            if identity['archiveSha256'] != value['archiveSha256']:
                raise ValueError('planned-source-archive-mismatch')
        # Qualification uses a maintained synthetic fixture, never real device calls.
        compatibility = runtime_package.qualify(current, target, directory / '.venv/bin/python',
                                                 staging / 'compatibility', Path(value['source']) / 'tests/fixtures/linux-state-v4/status.sql')
        copy_state(directory, staging / 'current-state')
        compatibility['currentStateReopenSha256'] = runtime_package.reopen_current(
            current, target, directory / '.venv/bin/python', staging / 'current-state')
        release.write(records / 'compatibility.json', compatibility)
        release.write(records / 'plan.json', value)
        return transition(value, target, identity, records / 'compatibility.json',
                          runtime_host.Host(directory, value['unitsDirectory']), lambda: check_plan(value))
    finally:
        try:
            shutil.rmtree(staging)
        finally:
            os.umask(prior_umask)


def refused(directory, requested, operation, code='qualification-or-plan-refused'):
    """A safe bounded reason; no exception text, credentials or private record contents."""
    now = timestamp()
    receipt = {'schemaVersion': 'install-receipt/1.0', 'operationId': 'nanoleaf-' + uuid.uuid4().hex,
               'operation': operation, 'runtime': 'nanoleaf', 'installationId': 'primary',
               'startedAt': now, 'updatedAt': now, 'completedAt': now, 'requestedTarget': requested,
               'previous': None, 'target': None, 'approval': None,
               'compatibility': {'status': 'unknown', 'evidence': None}, 'backup': None, 'running': None,
               'health': {'status': 'not-checked', 'evidence': None},
               'failure': {'phase': 'preflight', 'code': code, 'evidence': None},
               'rollback': {'status': 'not-attempted', 'evidence': None},
               'statePreservation': {'strategy': 'latest-durable-state', 'evidence': None}, 'outcome': 'refused'}
    path = private_directory(Path(directory) / 'receipts') / (receipt['operationId'] + '.json')
    persist(path, receipt)
    return receipt


def command(arguments):
    parser = argparse.ArgumentParser(description='Guarded complete-bundle Nanoleaf upgrades; no device commands.')
    parser.add_argument('command', choices=('plan', 'status', 'upgrade', 'rollback'))
    parser.add_argument('target', nargs='?')
    parser.add_argument('--state-dir', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--systemd-dir', type=Path, default=Path.home() / '.config/systemd/user')
    parser.add_argument('--operation', choices=('upgrade', 'rollback'), default='upgrade', help='Operation to bind when planning.')
    parser.add_argument('--plan', type=Path, help='Private exact plan JSON from the plan command; required for mutation.')
    parser.add_argument('--npm', default='npm', help='Native npm; shared Node and Python are never upgraded here.')
    args = parser.parse_args(arguments)
    try:
        if args.command == 'status':
            directory = args.state_dir.expanduser().absolute()
            _, identity = selected(directory)
            host = runtime_host.Host(directory, args.systemd_dir.expanduser().absolute())
            services = host.snapshot()
            try:
                _, main = source_identity(args.source_root, 'main')
            except (OSError, ValueError, subprocess.SubprocessError):
                main = None
            value = {'installed': identity,
                     'runningProcesses': {name: item['process'] if item['active'] == 'active' else None for name, item in services.items()},
                     'runningBuild': host.running_build(services), 'mergedMain': main,
                     'inspectionRequired': (directory / 'upgrade-records/active.json').exists()}
            print(json.dumps(value, indent=2))
            return 0
        if args.command == 'plan':
            requested = args.target or ('previous' if args.operation == 'rollback' else 'main')
            value = plan(args.state_dir, args.source_root, args.systemd_dir, requested, args.operation)
            print(json.dumps(value, indent=2))
            return 0
        if args.plan is None:
            raise ValueError('exact-plan-required')
        value = json.loads(args.plan.read_bytes())
        if Path(value['installation']) != args.state_dir.expanduser().absolute() or value['operation'] != args.command:
            raise ValueError('plan-operation-or-installation-mismatch')
        if args.target is not None and args.target != value['targetRevision']:
            raise ValueError('plan-target-mismatch')
        if args.command == 'upgrade' and args.target is None:
            raise ValueError('upgrade-full-sha-required')
        receipt = operate(value, args.npm)
        print(json.dumps(receipt, indent=2))
        return 0 if receipt['outcome'] == 'succeeded' else 1
    except FinalizationFailure as error:
        print(json.dumps(error.receipt), file=sys.stderr)
        return 1
    except Exception as error:
        # Read commands never create refusal records. Mutation refuses without
        # replay; any durable active intent remains an inspection barrier.
        if (args.command in ('upgrade', 'rollback') and args.state_dir.is_dir() and not args.state_dir.is_symlink()
                and args.state_dir.stat().st_uid == os.getuid() and (args.state_dir / 'runtime').is_dir()):
            try:
                print(json.dumps(refused(args.state_dir, args.target or 'previous', args.command, safe_code(error))), file=sys.stderr)
            except (OSError, ValueError):
                pass
        print('Nanoleaf upgrade refused or incomplete (' + safe_code(error) + '). Inspect the private plan, receipt and upgrade-records; do not retry an unresolved operation.', file=sys.stderr)
        return 1
