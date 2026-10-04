"""Fixed owning install/reconcile bridge for the shared delivery supervisor."""
import argparse
import contextlib
import fcntl
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time

sys.dont_write_bytecode = True
import install_contract
import runtime_host
import runtime_release as release
import runtime_upgrade as upgrade

REPOSITORY = 'jimmie-potts/codex-nanoleaf'
CONFIG_FIELDS = {'schemaVersion', 'owner', 'stateDirectory', 'sourceRoot', 'systemdDirectory',
                 'npm', 'evidenceRoot', 'transitionReserveSeconds'}
REQUEST_FIELDS = {'schemaVersion', 'operation', 'repository', 'issue', 'merge', 'owner',
                  'deadline', 'evidenceDirectory'}


class Refusal(ValueError):
    """Only fixed adapter-owned reason codes may enter protocol output."""


def reason(error):
    return str(error) if isinstance(error, Refusal) else upgrade.safe_code(error)


def require(condition, reason):
    if not condition:
        raise Refusal(reason)


def owned_path(value, *, directory=False, private=False):
    require(isinstance(value, str) and value and '\0' not in value, 'invalid-owned-path')
    path = Path(value)
    require(path.is_absolute() and path.resolve(strict=True) == path, 'owned-path-link-or-relative')
    info = path.lstat()
    require(info.st_uid == os.getuid() and (stat.S_ISDIR(info.st_mode) if directory else
            stat.S_ISREG(info.st_mode) and info.st_nlink == 1), 'unsupported-path-owner-or-type')
    require(not info.st_mode & (0o077 if private else 0o022), 'unsafe-owned-path-mode')
    return path


def strict_json(raw):
    def unique(pairs):
        result = {}
        for key, item in pairs:
            require(key not in result, 'duplicate-json-key')
            result[key] = item
        return result
    return json.loads(raw, object_pairs_hook=unique)


def configuration(path):
    path = owned_path(str(path), private=True)
    require(path.stat().st_size <= 16384, 'configuration-too-large')
    value = strict_json(path.read_bytes())
    require(isinstance(value, dict) and set(value) == CONFIG_FIELDS and
            type(value['schemaVersion']) is int and value['schemaVersion'] == 1, 'invalid-adapter-configuration')
    require(isinstance(value['owner'], str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.@-]{0,127}', value['owner']), 'invalid-named-owner')
    require(type(value['transitionReserveSeconds']) is int and 600 <= value['transitionReserveSeconds'] <= 3600,
            'insufficient-transition-reserve-configuration')
    for field in ('stateDirectory', 'sourceRoot', 'systemdDirectory', 'evidenceRoot'):
        owned_path(value[field], directory=True, private=field in ('stateDirectory', 'evidenceRoot'))
    npm = owned_path(value['npm'])
    require(os.access(npm, os.X_OK), 'native-npm-not-executable')
    return value


def request(value, config):
    require(isinstance(value, dict) and set(value) == REQUEST_FIELDS and type(value['schemaVersion']) is int and
            value['schemaVersion'] == 1 and value['operation'] in ('install', 'reconcile'), 'invalid-installation-request')
    require(value['repository'] == REPOSITORY and value['owner'] == config['owner'], 'installation-authority-mismatch')
    require(type(value['issue']) is int and value['issue'] > 0 and isinstance(value['merge'], str) and
            release.SHA.fullmatch(value['merge']), 'invalid-issue-or-merge')
    require(type(value['deadline']) in (int, float) and math.isfinite(value['deadline']), 'invalid-deadline')
    evidence = owned_path(value['evidenceDirectory'], directory=True, private=True)
    root = owned_path(config['evidenceRoot'], directory=True, private=True)
    require(evidence != root and evidence.is_relative_to(root), 'evidence-outside-configured-root')
    require(all(not parent.stat().st_mode & 0o077 and parent.stat().st_uid == os.getuid()
                for parent in [evidence, *evidence.parents] if parent.is_relative_to(root)), 'unsafe-evidence-parent')
    return value


def reserve(deadline, seconds):
    require(deadline - time.time() >= seconds, 'insufficient-installation-deadline-reserve')


def read_record(path):
    path = owned_path(str(path), private=True)
    require(path.stat().st_size <= 4 * 1024 * 1024, 'receipt-evidence-too-large')
    raw = path.read_bytes()
    return raw, json.loads(raw)


@contextlib.contextmanager
def inspection_lock(directory):
    # Inspection never creates a missing lock or changes installed state.
    path = owned_path(str(Path(directory) / 'upgrade.lock'), private=True)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        require(os.fstat(descriptor).st_ino == path.stat().st_ino, 'inspection-lock-replaced')
        fcntl.flock(descriptor, fcntl.LOCK_SH | fcntl.LOCK_NB)
        yield
    finally:
        os.close(descriptor)


def inspect(config, value):
    directory = Path(config['stateDirectory'])
    with inspection_lock(directory):
        upgrade.unresolved(directory)
        selected, identity = upgrade.selected(directory)
        require(identity['kind'] == 'release' and identity['sourceRevision'] == value['merge'], 'selected-revision-mismatch')
        _, marker = read_record(directory / 'upgrade-records/latest-success.json')
        operation = marker.get('operationId')
        require(isinstance(operation, str) and re.fullmatch(r'nanoleaf-[0-9a-f]{32}', operation), 'invalid-success-marker')
        path = directory / 'receipts' / (operation + '.json')
        raw, receipt = read_record(path)
        require(install_contract.validate_receipt(receipt) and receipt['operationId'] == operation and
                receipt['runtime'] == 'nanoleaf' and receipt['installationId'] == 'primary' and
                receipt['operation'] in ('upgrade', 'migrate') and receipt['outcome'] == 'succeeded' and
                receipt['requestedTarget'] == value['merge'] and receipt['target'] == identity and
                receipt['running']['identity'] == identity and receipt['health']['status'] == 'healthy',
                'exact-success-receipt-required')
        health_path = directory / 'upgrade-records' / operation / 'health.json'
        require(receipt['running']['evidence'] == str(health_path) and receipt['health']['evidence'] == str(health_path),
                'receipt-health-reference-mismatch')
        _, prior = read_record(health_path)
        require(set(prior['units']) == set(runtime_host.UNITS), 'receipt-process-evidence-incomplete')
        ticks = [item['process']['startTicks'] for item in prior['units'].values()]
        require(all(type(tick) is int and tick > 0 for tick in ticks), 'receipt-process-evidence-incomplete')
        host = runtime_host.Host(directory, config['systemdDirectory'])
        fresh = host.health(identity, selected, min(ticks))
        status = upgrade.status(directory, host)
        require(not status['inspectionRequired'] and status['installed'] == identity and
                status['runningBuild'] == {key: identity[key] for key in ('sourceRevision', 'version')} and
                all(runtime_host.same_process(fresh['units'][name]['process'], status['runningProcesses'][name])
                    for name in runtime_host.UNITS), 'fresh-running-readback-mismatch')
        upgrade.unresolved(directory)
        require(upgrade.selected(directory) == (selected, identity) and path.read_bytes() == raw,
                'installation-changed-during-readback')
        evidence = Path(value['evidenceDirectory'])
        release.write(evidence / 'readback.json', {'status': status, 'health': fresh,
                                                 'clientAcceptance': False, 'physicalAcceptance': False})
        return {'installedRevision': identity['sourceRevision'], 'runningRevision': status['runningBuild']['sourceRevision'],
                'health': 'healthy', 'receipt': {'path': str(path), 'sha256': release.digest(raw)}}


def inspect_settled_failure(config, value):
    directory = Path(config['stateDirectory'])
    _, exact = read_record(Path(value['evidenceDirectory']) / 'plan.json')
    require(exact['targetRevision'] == value['merge'] and exact['operation'] == 'upgrade' and
            exact['installation'] == str(directory) and exact['source'] == config['sourceRoot'] and
            exact['unitsDirectory'] == config['systemdDirectory'] and exact['planSha256'] ==
            release.digest(release.encoded({key: item for key, item in exact.items() if key != 'planSha256'})),
            'settled-failure-plan-mismatch')
    with inspection_lock(directory):
        upgrade.unresolved(directory)
        selected, identity = upgrade.selected(directory)
        require(identity == exact['previous'], 'settled-failure-baseline-mismatch')
        paths = list((directory / 'receipts').glob('nanoleaf-*.json'))
        require(len(paths) <= 1024, 'receipt-inspection-capacity')
        refusal = Path(value['evidenceDirectory']) / 'native-refusal.json'
        if refusal.exists(): paths.append(refusal)
        matches = []
        for path in paths:
            raw, receipt = read_record(path)
            if (receipt.get('approval') or {}).get('planSha256') == exact['planSha256']:
                require(install_contract.validate_receipt(receipt), 'invalid-terminal-native-receipt')
                if receipt['outcome'] in ('refused', 'failed-rolled-back'):
                    matches.append((path, raw, receipt))
        require(len(matches) == 1, 'ambiguous-terminal-native-receipt')
        path, raw, receipt = matches[0]
        require(receipt['runtime'] == 'nanoleaf' and receipt['installationId'] == 'primary' and
                receipt['requestedTarget'] == value['merge'] and receipt['previous'] == identity,
                'terminal-native-identity-mismatch')
        if receipt['outcome'] == 'failed-rolled-back':
            require(receipt['running']['identity'] == identity and receipt['health']['status'] == 'healthy',
                    'rollback-not-healthy')
        host = runtime_host.Host(directory, config['systemdDirectory'])
        fresh = host.health(identity, selected, 0)
        status = upgrade.status(directory, host)
        require(not status['inspectionRequired'] and status['installed'] == identity and
                all(runtime_host.same_process(fresh['units'][name]['process'], status['runningProcesses'][name])
                    for name in runtime_host.UNITS), 'settled-failure-running-mismatch')
        upgrade.unresolved(directory)
        require(upgrade.selected(directory) == (selected, identity) and path.read_bytes() == raw,
                'installation-changed-during-readback')
        release.write(Path(value['evidenceDirectory']) / 'failure-readback.json', {'status': status, 'health': fresh})
        return {'status': 'blocked', 'effects': 'none' if receipt['outcome'] == 'refused' else 'reconciled',
                'outcome': receipt['outcome'], 'baselineIdentity': identity, 'runningIdentity': identity,
                'health': 'healthy', 'locksClear': True, 'barriersClear': True,
                'receipt': {'path': str(path), 'sha256': release.digest(raw)}}


def execute(config, value, config_guard=lambda: None):
    value = request(value, config)
    response = {key: value[key] for key in ('schemaVersion', 'repository', 'issue', 'merge', 'owner')}
    dispatched = False
    exact = None
    try:
        reserve(value['deadline'], 1)
        if value['operation'] == 'install':
            reserve(value['deadline'], config['transitionReserveSeconds'] + 30)
            config_guard()
            with runtime_host.preflight_deadline(value['deadline'] - config['transitionReserveSeconds']):
                exact = upgrade.plan(config['stateDirectory'], config['sourceRoot'], config['systemdDirectory'], value['merge'])
            require(exact['targetRevision'] == value['merge'] and exact['operation'] == 'upgrade' and
                    exact['installation'] == config['stateDirectory'] and exact['source'] == config['sourceRoot'] and
                    exact['unitsDirectory'] == config['systemdDirectory'], 'native-plan-request-mismatch')
            plan_path = Path(value['evidenceDirectory']) / 'plan.json'
            release.write(plan_path, exact)
            require(json.loads(plan_path.read_bytes()) == exact, 'plan-readback-mismatch')
            def before_stop():
                config_guard()
                reserve(value['deadline'], config['transitionReserveSeconds'])
            dispatched = True
            receipt = upgrade.operate(exact, config['npm'], deadline=value['deadline'] - config['transitionReserveSeconds'],
                                      before_stop=before_stop)
            require(install_contract.validate_receipt(receipt) and receipt['outcome'] == 'succeeded', 'native-upgrade-incomplete')
        config_guard()
        with runtime_host.preflight_deadline(value['deadline']):
            observed = inspect(config, value)
        reserve(value['deadline'], 0)
        return response | {'status': 'installed'} | observed
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError) as error:
        try:
            config_guard()
            if dispatched and exact is not None and (isinstance(error, upgrade.PreflightRefusal) or
                    isinstance(error, Refusal) and str(error) == 'insufficient-installation-deadline-reserve'):
                upgrade.refused(config['stateDirectory'], value['merge'], 'upgrade',
                                reason(error),
                                output_path=Path(value['evidenceDirectory']) / 'native-refusal.json', plan=exact)
            with runtime_host.preflight_deadline(value['deadline']):
                settled = inspect_settled_failure(config, value)
            reserve(value['deadline'], 0)
            return response | settled
        except (OSError, ValueError, KeyError, TypeError, RuntimeError, AttributeError, subprocess.SubprocessError):
            pass  # Missing proof stays uncertain; never replay or remove a barrier.
        return response | {'status': 'uncertain' if dispatched or value['operation'] == 'reconcile' else 'blocked',
                           'reason': reason(error)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    try:
        config = configuration(args.config)
        raw = sys.stdin.buffer.read(65537)
        require(len(raw) <= 65536, 'request-too-large')
        value = strict_json(raw)
        def guard():
            require(configuration(args.config) == config, 'trusted-configuration-changed')
        result = execute(config, value, guard)
        print(json.dumps(result))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({'schemaVersion': 1, 'status': 'blocked', 'reason': reason(error)}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
