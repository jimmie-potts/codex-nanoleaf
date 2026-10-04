"""Guarded upgrade contracts over isolated files and fake process/service effects."""
import json
import contextlib
import os
from pathlib import Path
import sys
import tempfile
import sqlite3
import shutil
import subprocess
from unittest import mock
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'bridge'))


class ReceiptContractTest(unittest.TestCase):
    def test_published_receipt_corpus_is_consumed_without_changing_controller_contract(self):
        import install_contract
        corpus = json.loads((install_contract.ROOT / 'package/fixtures/install-receipt-v1.json').read_text())
        self.assertGreater(len(corpus['cases']), 0)
        for case in corpus['cases']:
            with self.subTest(case=case['id']):
                self.assertEqual(install_contract.validate_receipt(case['value']), case['valid'])

    def test_pinned_contract_archive_tamper_is_rejected_before_loading(self):
        import install_contract
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'contract'
            shutil.copytree(install_contract.ROOT, root)
            archive = root / 'jimmie-potts-device-contracts-1.2.0.tgz'
            archive.write_bytes(archive.read_bytes() + b'tampered')
            with self.assertRaises(ValueError):
                install_contract.verify(root)


class ReleaseTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def package(self):
        import runtime_release as release
        for name in ('bridge', 'mcp', 'vendor'):
            (self.root / name).mkdir()
            (self.root / name / 'payload').write_text(name)
        return release.seal(self.root, 'a' * 40, '0.4.0', b'exact git archive')

    def test_complete_inventory_rejects_tamper_extra_files_and_escaping_links(self):
        import runtime_release as release
        identity = self.package()
        self.assertEqual(release.verify(self.root), identity)
        extra = self.root / 'mcp' / 'unreviewed'
        extra.write_text('new entry')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            release.verify(self.root)
        extra.unlink()
        (self.root / 'vendor' / 'payload').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            release.verify(self.root)
        (self.root / 'vendor' / 'payload').unlink()
        (self.root / 'vendor' / 'payload').symlink_to('/etc/passwd')
        with self.assertRaisesRegex(ValueError, 'link'):
            release.verify(self.root)

    def test_build_identity_is_captured_from_own_release_not_later_current_link(self):
        import runtime_release as release
        identity = self.package()
        build = release.build(self.root / 'bridge' / 'controller_server.py')
        self.assertEqual(build, {'sourceRevision': identity['sourceRevision'], 'version': '0.4.0'})
        (self.root / 'release.json').write_text('{}')
        self.assertEqual(build['sourceRevision'], 'a' * 40)
        self.assertEqual(release.build(self.root / 'bridge' / 'controller_server.py'),
                         {'sourceRevision': 'unknown', 'version': 'unknown'})

    def test_release_dependencies_are_read_from_the_bundle_without_changing_shared_python(self):
        import runtime_package
        dependencies = self.root / 'bridge/python-deps'
        metadata = dependencies / 'upgrade_fixture-1.0.dist-info'
        metadata.mkdir(parents=True)
        (metadata / 'METADATA').write_text('Metadata-Version: 2.1\nName: upgrade-fixture\nVersion: 1.0\n')
        (self.root / 'bridge/requirements-controller.txt').write_text('upgrade-fixture==1.0\n')
        runtime_package.verify_dependencies(self.root, sys.executable)
        (metadata / 'METADATA').write_text('Metadata-Version: 2.1\nName: upgrade-fixture\nVersion: 2.0\n')
        with self.assertRaises(subprocess.CalledProcessError):
            runtime_package.verify_dependencies(self.root, sys.executable)


class TransitionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ('bridge', 'mcp', 'vendor', 'hub-gh30', 'node'):
            path = self.root / 'runtime' / name
            path.mkdir(parents=True)
            (path / 'marker').write_text(name)
        (self.root / 'records').mkdir()

    def test_fence_records_inode_and_mode_before_denying_entry_and_restores_them(self):
        import runtime_upgrade as upgrade
        program = self.root / 'runtime/bridge'
        original = program.stat()
        with upgrade.Fence([program], self.root / 'records/fence.json'):
            self.assertEqual(program.stat().st_mode & 0o111, 0)
            evidence = json.loads((self.root / 'records/fence.json').read_bytes())
            self.assertEqual(evidence[0]['inode'], original.st_ino)
            self.assertEqual(evidence[0]['mode'], original.st_mode & 0o777)
        self.assertEqual(program.stat().st_mode, original.st_mode)
        self.assertEqual(program.stat().st_ino, original.st_ino)
        self.assertEqual((self.root / 'runtime/hub-gh30/marker').read_text(), 'hub-gh30')

    def test_partial_adoption_is_an_inspection_barrier_and_never_replaces_runtime_parent(self):
        import runtime_upgrade as upgrade
        parent = (self.root / 'runtime').stat().st_ino
        selected = self.root / 'legacy/first'
        selected.mkdir(parents=True)
        with self.assertRaisesRegex(RuntimeError, 'interrupted'):
            upgrade.adopt(self.root, selected, lambda index: (_ for _ in ()).throw(RuntimeError('interrupted')) if index == 1 else None)
        self.assertEqual((self.root / 'runtime').stat().st_ino, parent)
        self.assertTrue((selected / 'bridge').is_dir())
        self.assertEqual(os.readlink(self.root / 'runtime/bridge'), '../current/bridge')
        self.assertFalse((self.root / 'runtime/mcp').is_symlink())
        self.assertEqual((self.root / 'runtime/node/marker').read_text(), 'node')

    def test_plan_binding_ignores_mutable_database_but_not_credentials_or_bundle(self):
        import runtime_upgrade as upgrade
        (self.root / 'config.json').write_text('{"token":"private"}')
        with contextlib.closing(sqlite3.connect(self.root / 'status.sqlite')) as db, db:
            db.execute('CREATE TABLE state(value TEXT)')
            db.execute("INSERT INTO state VALUES ('old')")
        before = upgrade.configuration(self.root)
        with contextlib.closing(sqlite3.connect(self.root / 'status.sqlite')) as db, db:
            db.execute("UPDATE state SET value='new'")
        self.assertEqual(upgrade.configuration(self.root), before)
        (self.root / 'config.json').write_text('{"token":"changed"}')
        self.assertNotEqual(upgrade.configuration(self.root), before)
        self.assertNotIn('private', json.dumps(before))

    def test_exact_plan_is_read_only_and_binds_unknown_legacy_comparison(self):
        import runtime_upgrade as upgrade
        import runtime_release as release
        (self.root / 'config.json').write_text('{"token":"private"}')
        # The generic record fixture is not a named installed state directory.
        (self.root / 'records').rmdir()
        host = mock.Mock()
        host.snapshot.return_value = {'fixture.service': {'sha256': 'c' * 64, 'argv': ['fixture'], 'active': 'active', 'process': None}}
        host.running_build.return_value = {'sourceRevision': 'unknown', 'version': 'unknown'}
        before = release.inventory(self.root)
        with mock.patch.object(upgrade, 'source_identity', return_value=('a' * 40, 'a' * 40)), mock.patch.object(upgrade, 'git', return_value=b'exact archive'):
            value = upgrade.plan(self.root, ROOT, self.root / 'units', 'a' * 40, host=host)
        self.assertEqual(release.inventory(self.root), before)
        self.assertIsNone(value['commits'])
        self.assertIsNone(value['changedPaths'])
        self.assertEqual(value['runningBuild']['sourceRevision'], 'unknown')
        self.assertEqual(value['archiveSha256'], release.digest(b'exact archive'))
        self.assertNotIn('private', json.dumps(value))

    def test_shared_state_and_retained_history_are_bound_but_never_adopted_or_backed_up(self):
        import runtime_upgrade as upgrade
        import runtime_release as release
        siblings = ('shared-monitor', 'install-backups', '.npm-cache',
                    'runtime/hub-gh30.prev-op-example', 'runtime/bridge-before-gh30', 'runtime/codex-gh30')
        for name in siblings:
            path = self.root / name
            path.mkdir()
            (path / 'private-original').write_text(name)
        host = mock.Mock()
        host.snapshot.return_value = {}
        host.running_build.return_value = None
        before = release.inventory(self.root)
        with mock.patch.object(upgrade, 'source_identity', return_value=('a' * 40, 'a' * 40)), mock.patch.object(upgrade, 'git', return_value=b'archive'):
            value = upgrade.plan(self.root, ROOT, self.root / 'units', 'a' * 40, host=host)
        self.assertEqual(release.inventory(self.root), before)
        self.assertTrue(set(siblings).issubset(value['protected']['untouchedSiblings']))
        backup = self.root / 'upgrade-backups/fixture'
        upgrade.copy_state(self.root, backup)
        self.assertEqual(list(backup.iterdir()), [])
        retained = self.root / 'legacy/first'
        retained.mkdir(parents=True)
        upgrade.adopt(self.root, retained)
        for name in siblings:
            self.assertEqual((self.root / name / 'private-original').read_text(), name)
        self.assertEqual(upgrade.protected(self.root), value['protected'])
        (self.root / 'shared-monitor/private-original').write_text('normal live owner write')
        self.assertEqual(upgrade.protected(self.root), value['protected'])
        (self.root / 'shared-monitor').rename(self.root / 'shared-monitor-old')
        (self.root / 'shared-monitor').mkdir()
        self.assertNotEqual(upgrade.protected(self.root), value['protected'])

    def test_owned_record_path_cannot_escape_through_parent_symlink(self):
        import runtime_upgrade as upgrade
        outside = self.root / 'other-owner'
        outside.mkdir()
        (self.root / 'upgrade-records').symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'link'):
            upgrade.private_directory(self.root / 'upgrade-records/operation')
        self.assertEqual(list(outside.iterdir()), [])

    def test_dirty_source_refuses_before_remote_lookup_or_archive_build(self):
        import runtime_upgrade as upgrade
        with mock.patch.object(upgrade, 'git', return_value=b' M bridge/bridge.py\n') as command:
            with self.assertRaisesRegex(ValueError, 'dirty'):
                upgrade.source_identity(ROOT, 'a' * 40)
            self.assertEqual(command.call_count, 1)

    def test_inactive_controller_does_not_make_a_running_build_claim(self):
        import runtime_host
        host = runtime_host.Host(self.root, self.root / 'units')
        with mock.patch.object(host, 'http') as http:
            value = host.running_build({runtime_host.UNITS[1]: {'active': 'inactive', 'process': None}})
        self.assertIsNone(value)
        http.assert_not_called()

    def test_permission_fence_blocks_new_entry_and_drains_preopened_owned_process(self):
        import runtime_upgrade as upgrade
        import runtime_host
        if os.getuid() == 0:
            self.skipTest('root cannot qualify an ordinary-user permission fence')
        program = self.root / 'runtime/bridge'
        script = program / 'bridge.py'
        script.write_text('import time\nprint("opened",flush=True)\ntime.sleep(30)\n')
        child = subprocess.Popen([sys.executable, str(script)], stdout=subprocess.PIPE, text=True)
        def cleanup_child():
            if child.poll() is None:
                child.kill()
            child.wait(timeout=2)
        self.addCleanup(cleanup_child)
        self.addCleanup(child.stdout.close)
        self.assertEqual(child.stdout.readline().strip(), 'opened')
        host = runtime_host.Host(self.root, self.root / 'units')
        before = host.owned_processes([program])
        self.assertEqual([info['pid'] for info in before], [child.pid])
        with upgrade.Fence([program], self.root / 'records/fence.json'):
            refused = subprocess.run([sys.executable, str(script)], capture_output=True, timeout=2)
            self.assertNotEqual(refused.returncode, 0)
            with mock.patch.object(runtime_host, 'run') as command, mock.patch.object(host, 'service', return_value={'ActiveState': 'inactive'}):
                host.stop([program])
                self.assertEqual(command.call_args.args[0][:3], ['systemctl', '--user', 'stop'])
            child.wait(timeout=2)
            self.assertEqual(host.owned_processes([program]), [])


class ReadbackHealthTest(unittest.TestCase):
    def test_inspection_avoids_the_wall_metadata_refresh_and_worker_launch_route(self):
        import runtime_host
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'bridge').mkdir()
            page = b'<html>ready</html>'
            (root / 'bridge/wall.html').write_bytes(page)
            (root / 'config.json').write_text(json.dumps({'wall_port': 8765, 'controller_port': 41231, 'mcp_port': 41230}))
            (root / 'mcp-credentials.json').write_text(json.dumps({'principals': [{'scopes': ['read'], 'upstreamToken': 'fixture'}]}))
            (root / 'mcp-client-token').write_text('fixture')
            marker = root / 'mutable-state'
            marker.write_text('latest')
            launches = []
            paths = []

            def http(port, path, token=None, body=None, headers=None):
                paths.append(path)
                if path == '/':
                    return page, {}
                if path == '/api/state':
                    # The existing browser state route refreshes metadata and
                    # launches a worker when it changes. Inspection must avoid it.
                    marker.write_text('metadata-refreshed')
                    launches.append('worker')
                    return b'{}', {}
                if path == '/api/rendering':
                    return b'{}', {}
                if path == '/controller/v1/devices':
                    return b'{"devices":[{"id":"fixture"}]}', {}
                if path == '/mcp':
                    if body['method'] == 'initialize':
                        return b'{"result":{}}', {'Mcp-Session-Id': 'fixture'}
                    if body['method'] == 'notifications/initialized':
                        return b'', {}
                    if body['method'] == 'tools/list':
                        return b'{"result":{"tools":[{"name":"nanoleaf_status"}]}}', {}
                raise AssertionError('unexpected health request')

            host = runtime_host.Host(root, root)
            services = {name: {'active': 'active', 'process': {'startTicks': 10}} for name in runtime_host.UNITS}
            with mock.patch.object(host, 'snapshot', return_value=services), \
                    mock.patch.object(host, 'owned_processes', return_value=[]), \
                    mock.patch.object(host, 'http', side_effect=http):
                observed = host.health({'kind': 'legacy'}, root, 0)
            self.assertEqual(marker.read_text(), 'latest', 'inspection refreshed mutable state')
            self.assertEqual(launches, [], 'inspection launched a worker')
            self.assertEqual(observed['mcp'], 'authenticated-discovery')
            self.assertIn('/api/rendering', paths)


class FakeHost:
    def __init__(self, root, fail_target=False, fail_recovery=False):
        self.root = root
        self.calls = []
        self.fail_target = fail_target
        self.fail_recovery = fail_recovery

    def stop(self, roots):
        self.calls.append('stop')
        for name in ('bridge', 'mcp'):
            path = self.root / 'runtime' / name
            if path.exists():
                assert path.stat().st_mode & 0o111 == 0

    def start(self):
        self.calls.append('start')

    @contextlib.contextmanager
    def worker_locks(self):
        self.calls.append('locks')
        yield

    def health(self, identity, selected, started_after, *, inspection=True):
        assert not inspection, 'a transition must perform its post-start health check'
        self.calls.append('health-' + identity['kind'])
        if identity['kind'] == 'release' and self.fail_target:
            (self.root / 'scene-state.json').write_text('{"newer":"write"}')
            raise ValueError('candidate-health-failed')
        if identity['kind'] == 'legacy' and self.fail_recovery:
            raise ValueError('recovery-health-failed')
        return {'fakeServices': True, 'physicalAcceptance': False}


class ServiceOwnershipTest(unittest.TestCase):
    def test_additional_unit_dependencies_and_alternate_state_arguments_refuse(self):
        import install_linux
        import runtime_host
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'config.json').write_text(json.dumps({'wall_port': 8765, 'controller_port': 41231, 'mcp_port': 41230}))
            units = root / 'units'
            install_linux.write_service_units(root, units, root / '.venv/bin/python', root / 'runtime/node/bin/node')
            host = runtime_host.Host(root, units)
            def service(name):
                return {'FragmentPath': str(units / name), 'MainPID': '0', 'ActiveState': 'inactive',
                        'DropInPaths': '', 'User': '', 'AmbientCapabilities': '', 'NeedDaemonReload': 'no'}
            with mock.patch.object(host, 'service', side_effect=service):
                self.assertEqual(len(host.snapshot()), 3)
                path = units / runtime_host.UNITS[0]
                original = path.read_text()
                path.write_text(original.replace('[Unit]', '[Unit]\nPropagatesStopTo=other-owner.service'))
                with self.assertRaisesRegex(ValueError, 'effects'):
                    host.snapshot()
                path.write_text(original.replace('"--state-dir" "' + str(root) + '"', '"--state-dir" "/another-owner"'))
                with self.assertRaisesRegex(ValueError, 'command'):
                    host.snapshot()


class OperationTest(unittest.TestCase):
    def setUp(self):
        import runtime_upgrade as upgrade
        import runtime_release as release
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'installation'
        self.root.mkdir()
        for name in (*release.COMPONENTS, 'node', 'hub-gh30'):
            path = self.root / 'runtime' / name
            path.mkdir(parents=True)
            (path / 'payload').write_text(name)
        (self.root / 'config.json').write_text('{}')
        with contextlib.closing(sqlite3.connect(self.root / 'status.sqlite')) as db, db:
            db.execute('CREATE TABLE durable(value TEXT)')
            db.execute("INSERT INTO durable VALUES ('latest')")
        self.previous = upgrade.selected(self.root)[1]
        self.target = Path(self.temp.name) / 'candidate'
        for name in release.COMPONENTS:
            (self.target / name).mkdir(parents=True)
            (self.target / name / 'payload').write_text('new-' + name)
        self.identity = release.seal(self.target, 'a' * 40, '1.0.0', b'trusted source')
        self.value = {'installation': str(self.root), 'requestedTarget': 'a' * 40, 'operation': 'upgrade',
                      'previous': self.previous, 'configuration': upgrade.configuration(self.root),
                      'protected': upgrade.protected(self.root), 'planSha256': 'b' * 64}
        self.compatibility = self.root / 'compatibility.json'
        self.compatibility.write_text('{}')

    def test_complete_adoption_and_receipt_keep_other_owner_unchanged(self):
        import runtime_upgrade as upgrade
        import install_contract
        host = FakeHost(self.root)
        receipt = upgrade.transition(self.value, self.target, self.identity, self.compatibility, host, lambda: None)
        self.assertEqual(receipt['outcome'], 'succeeded')
        self.assertTrue(install_contract.validate_receipt(receipt))
        self.assertEqual(upgrade.selected(self.root)[1], self.identity)
        self.assertEqual(host.calls, ['stop', 'locks', 'start', 'health-release'])
        self.assertEqual(upgrade.protected(self.root), self.value['protected'])

    def test_failed_candidate_recovers_previous_without_restoring_newer_state(self):
        import runtime_upgrade as upgrade
        host = FakeHost(self.root, fail_target=True)
        receipt = upgrade.transition(self.value, self.target, self.identity, self.compatibility, host, lambda: None)
        self.assertEqual(receipt['outcome'], 'failed-rolled-back')
        self.assertEqual(json.loads((self.root / 'scene-state.json').read_bytes()), {'newer': 'write'})
        self.assertEqual(upgrade.selected(self.root)[1], self.previous)
        self.assertEqual(upgrade.protected(self.root), self.value['protected'])

    def test_failed_recovery_retains_barrier(self):
        import runtime_upgrade as upgrade
        host = FakeHost(self.root, fail_target=True, fail_recovery=True)
        receipt = upgrade.transition(self.value, self.target, self.identity, self.compatibility, host, lambda: None)
        self.assertEqual(receipt['outcome'], 'rollback-failed')
        with self.assertRaisesRegex(ValueError, 'inspection'):
            upgrade.unresolved(self.root)

    def test_drift_refuses_before_stopping_and_lock_prevents_concurrent_transition(self):
        import runtime_upgrade as upgrade
        host = FakeHost(self.root)
        def drift():
            raise ValueError('plan-drift')
        with self.assertRaisesRegex(ValueError, 'plan-drift'):
            upgrade.transition(self.value, self.target, self.identity, self.compatibility, host, drift)
        self.assertEqual(host.calls, [])

    def test_final_receipt_failure_retains_intent_and_prevents_retry_or_pruning(self):
        import runtime_upgrade as upgrade
        import install_contract
        def disk_failure(*_):
            raise OSError('fixture disk failure')
        with self.assertRaises(upgrade.FinalizationFailure) as failure:
            upgrade.transition(self.value, self.target, self.identity, self.compatibility, FakeHost(self.root), lambda: None, final_writer=disk_failure)
        self.assertTrue(install_contract.validate_receipt(failure.exception.receipt))
        self.assertEqual(failure.exception.receipt['outcome'], 'receipt-finalization-failed')
        durable = json.loads(next((self.root / 'receipts').glob('*.json')).read_bytes())
        self.assertEqual(durable['outcome'], 'in-progress')
        with self.assertRaisesRegex(ValueError, 'inspection'):
            upgrade.unresolved(self.root)

    def test_adoption_interruption_preserves_originals_and_blocks_replay(self):
        import runtime_upgrade as upgrade
        for boundary in (1, 2, 3):
            with self.subTest(boundary=boundary):
                if boundary > 1:
                    self.doCleanups(); self.setUp()
                def fail(step):
                    if step == boundary:
                        raise OSError('fixture interruption')
                receipt = upgrade.transition(self.value, self.target, self.identity, self.compatibility, FakeHost(self.root), lambda: None, checkpoint=fail)
                self.assertEqual(receipt['outcome'], 'interrupted')
                self.assertTrue((self.root / 'runtime').is_dir())
                self.assertFalse((self.root / 'runtime').is_symlink())
                self.assertEqual(upgrade.protected(self.root), self.value['protected'])
                with self.assertRaisesRegex(ValueError, 'inspection'):
                    upgrade.unresolved(self.root)

    def test_explicit_rollback_to_legacy_is_success_with_latest_state(self):
        import runtime_upgrade as upgrade
        first = upgrade.transition(self.value, self.target, self.identity, self.compatibility, FakeHost(self.root), lambda: None)
        path, previous = upgrade.rollback_target(self.root, 'previous')
        self.assertEqual(previous, self.previous)
        self.value.update(previous=self.identity, operation='rollback', requestedTarget='previous')
        receipt = upgrade.transition(self.value, path, previous, self.compatibility, FakeHost(self.root), lambda: None)
        self.assertEqual(first['outcome'], 'succeeded')
        self.assertEqual(receipt['outcome'], 'succeeded')
        self.assertEqual(receipt['operation'], 'rollback')
        self.assertEqual(receipt['rollback']['status'], 'not-attempted')

    def test_python_and_state_probe_use_exact_target_and_previous_code(self):
        import runtime_package
        evidence = runtime_package.qualify(ROOT, ROOT, sys.executable, Path(self.temp.name) / 'probe', ROOT / 'tests/fixtures/linux-state-v4/status.sql')
        self.assertEqual(evidence['status'], 'compatible')
        self.assertEqual(evidence['probe'], 'target-write-previous-reopen')
        self.assertFalse(evidence['latestStateRestoredFromBackup'])

    def test_unrecognized_durable_code_refuses_before_dependency_or_state_work(self):
        import runtime_package
        with mock.patch.object(runtime_package, 'durable_fingerprint', side_effect=['a' * 64, 'b' * 64]), mock.patch.object(runtime_package, 'verify_dependencies') as dependencies:
            with self.assertRaisesRegex(ValueError, 'durable-implementation-unqualified'):
                runtime_package.qualify(ROOT, ROOT, sys.executable, Path(self.temp.name) / 'probe', ROOT / 'tests/fixtures/linux-state-v4/status.sql')
        dependencies.assert_not_called()

    def test_same_sha_different_bytes_and_concurrent_operation_refuse_before_stop(self):
        import runtime_upgrade as upgrade
        import fcntl
        host = FakeHost(self.root)
        with (self.root / 'upgrade.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                upgrade.transition(self.value, self.target, self.identity, self.compatibility, host, lambda: None)
        existing = self.root / 'releases' / self.identity['sourceRevision']
        shutil.copytree(self.target, existing)
        (existing / 'bridge/payload').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            upgrade.transition(self.value, self.target, self.identity, self.compatibility, host, lambda: None)
        self.assertEqual(host.calls, [])

    def test_backup_failure_never_switches_or_restarts(self):
        import runtime_upgrade as upgrade
        host = FakeHost(self.root)
        with mock.patch.object(upgrade, 'copy_state', side_effect=OSError('fixture backup failure')):
            receipt = upgrade.transition(self.value, self.target, self.identity, self.compatibility, host, lambda: None)
        self.assertEqual(receipt['outcome'], 'failed-before-switch')
        self.assertEqual(receipt['failure']['phase'], 'backup')
        self.assertEqual(host.calls, ['stop', 'locks'])
        self.assertEqual(upgrade.selected(self.root)[1], self.previous)

    def test_retention_keeps_current_three_previous_and_unknown_or_other_owner_history(self):
        import runtime_upgrade as upgrade
        import runtime_release as release
        unknown = self.root / 'releases/unrecognized-history'
        unknown.mkdir(parents=True)
        (unknown / 'marker').write_text('preserve')
        for index in range(6):
            candidate = Path(self.temp.name) / ('candidate-' + str(index))
            shutil.copytree(self.target, candidate)
            identity = release.seal(candidate, str(index + 1) * 40, '1.0.0', ('source-' + str(index)).encode())
            self.value['previous'] = upgrade.selected(self.root)[1]
            receipt = upgrade.transition(self.value, candidate, identity, self.compatibility, FakeHost(self.root), lambda: None)
            self.assertEqual(receipt['outcome'], 'succeeded')
        self.assertEqual({path.name for path in (self.root / 'releases').iterdir()},
                         {'3' * 40, '4' * 40, '5' * 40, '6' * 40, 'unrecognized-history'})
        self.assertEqual((unknown / 'marker').read_text(), 'preserve')
        self.assertEqual(len(list((self.root / 'legacy').iterdir())), 1)
        self.assertEqual(upgrade.protected(self.root), self.value['protected'])
        self.assertEqual(upgrade.rollback_target(self.root, 'previous')[1]['sourceRevision'], '5' * 40)


if __name__ == '__main__':
    unittest.main()
