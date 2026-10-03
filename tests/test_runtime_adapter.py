"""Owning supervisor protocol, with isolated installs and no live service effects."""
import json
import os
import sqlite3
import contextlib
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge'))


class AdapterTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for name in ('state', 'source', 'units', 'evidence', 'evidence/attempt'):
            (self.root / name).mkdir(mode=0o700)
        (self.root / 'npm').write_text('native npm')
        (self.root / 'npm').chmod(0o700)
        self.config = {'schemaVersion': 1, 'owner': 'jimmie',
                       'stateDirectory': str(self.root / 'state'), 'sourceRoot': str(self.root / 'source'),
                       'systemdDirectory': str(self.root / 'units'), 'npm': str(self.root / 'npm'),
                       'evidenceRoot': str(self.root / 'evidence'), 'transitionReserveSeconds': 600}
        self.path = self.root / 'adapter.json'
        self.path.write_text(json.dumps(self.config)); self.path.chmod(0o600)
        self.request = {'schemaVersion': 1, 'operation': 'install', 'repository': 'jimmie-potts/codex-nanoleaf',
                        'issue': 140, 'merge': 'a' * 40, 'owner': 'jimmie', 'deadline': time.time() + 900,
                        'evidenceDirectory': str(self.root / 'evidence/attempt')}

    def test_private_fixed_authority_and_request_are_strict(self):
        import runtime_adapter as adapter
        config = adapter.configuration(self.path)
        self.assertEqual(adapter.request(self.request, config), self.request)
        for change in ({'owner': 'other'}, {'repository': 'other/repo'}, {'merge': 'main'},
                       {'issue': True}, {'extra': 1}, {'deadline': float('nan')},
                       {'evidenceDirectory': str(self.root / 'source')}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                adapter.request(self.request | change, config)
        self.path.chmod(0o644)
        with self.assertRaises(ValueError):
            adapter.configuration(self.path)

    def test_insufficient_deadline_never_plans_or_installs(self):
        import runtime_adapter as adapter
        with mock.patch.object(adapter.upgrade, 'plan') as plan, mock.patch.object(adapter.upgrade, 'operate') as operate:
            result = adapter.execute(self.config, self.request | {'deadline': time.time() + 30})
        self.assertEqual(result['status'], 'blocked')
        plan.assert_not_called(); operate.assert_not_called()

    def test_reconcile_with_unresolved_intent_is_inspection_only(self):
        import runtime_adapter as adapter
        records = self.root / 'state/upgrade-records'; records.mkdir()
        (records / 'active.json').write_text('{}')
        with mock.patch.object(adapter.upgrade, 'plan') as plan, mock.patch.object(adapter.upgrade, 'operate') as operate:
            result = adapter.execute(self.config, self.request | {'operation': 'reconcile'})
        self.assertEqual(result['status'], 'uncertain')
        plan.assert_not_called(); operate.assert_not_called()

    def installed_fixture(self, fail_target=False):
        import runtime_adapter as adapter
        import runtime_host
        import runtime_release as release
        from test_runtime_install import FakeHost
        state = self.root / 'state'
        with contextlib.closing(sqlite3.connect(state / 'status.sqlite')) as db, db:
            db.execute('CREATE TABLE durable(value TEXT)')
            db.execute("INSERT INTO durable VALUES ('latest')")
        for name in release.COMPONENTS:
            (state / 'runtime' / name).mkdir(parents=True)
            (state / 'runtime' / name / 'payload').write_text(name)
            (self.root / 'candidate' / name).mkdir(parents=True)
            (self.root / 'candidate' / name / 'payload').write_text('new-' + name)
        identity = release.seal(self.root / 'candidate', 'a' * 40, '1.0.0', b'source')
        class Host(FakeHost):
            def snapshot(self):
                return {name: {'active': 'active', 'process': {'pid': index + 1000, 'startTicks': 1000,
                        'uid': os.getuid(), 'argv': [name]}} for index, name in enumerate(runtime_host.UNITS)}
            def health(self, identity, selected, started_after):
                if fail_target and identity['kind'] == 'release':
                    raise ValueError('candidate-health-failed')
                return {'units': self.snapshot(), 'fakeServices': True}
            def running_build(self, services):
                return {key: identity[key] for key in ('sourceRevision', 'version')}
        host = Host(state)
        plan = {'installation': str(state), 'source': self.config['sourceRoot'], 'unitsDirectory': self.config['systemdDirectory'],
                'targetRevision': 'a' * 40, 'requestedTarget': 'a' * 40, 'operation': 'upgrade',
                'previous': adapter.upgrade.selected(state)[1], 'configuration': adapter.upgrade.configuration(state),
                'protected': adapter.upgrade.protected(state), 'planSha256': 'b' * 64}
        plan['planSha256'] = release.digest(release.encoded({key: value for key, value in plan.items() if key != 'planSha256'}))
        receipt = adapter.upgrade.transition(plan, self.root / 'candidate', identity, self.root / 'compatibility', host, lambda: None)
        self.assertEqual(receipt['outcome'], 'failed-rolled-back' if fail_target else 'succeeded')
        return host, receipt, plan

    def test_reconciled_legacy_rollback_parks_without_reinstall_or_installed_claim(self):
        import runtime_adapter as adapter
        host, receipt, plan = self.installed_fixture(fail_target=True)
        adapter.release.write(self.root / 'evidence/attempt/plan.json', plan)
        with mock.patch.object(adapter.runtime_host, 'Host', return_value=host), mock.patch.object(adapter.upgrade, 'operate') as operate:
            result = adapter.execute(self.config, self.request | {'operation': 'reconcile'})
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(result['effects'], 'reconciled')
        self.assertEqual(result['outcome'], 'failed-rolled-back')
        self.assertEqual(result['baselineIdentity'], plan['previous'])
        self.assertEqual(result['runningIdentity'], plan['previous'])
        self.assertTrue(result['barriersClear'])
        self.assertNotIn('installedRevision', result)
        operate.assert_not_called()
        adapter.release.write(self.root / 'state/upgrade-records/active.json', {})
        with mock.patch.object(adapter.runtime_host, 'Host', return_value=host):
            self.assertEqual(adapter.execute(self.config, self.request | {'operation': 'reconcile'})['status'], 'uncertain')

    def test_reconcile_verifies_semantic_receipt_and_fresh_build_health_without_reinstall(self):
        import runtime_adapter as adapter
        host, receipt, _ = self.installed_fixture()
        with mock.patch.object(adapter.runtime_host, 'Host', return_value=host), mock.patch.object(adapter.upgrade, 'operate') as operate:
            result = adapter.execute(self.config, self.request | {'operation': 'reconcile'})
        self.assertEqual(result['status'], 'installed')
        self.assertEqual(result['runningRevision'], self.request['merge'])
        self.assertEqual(result['installedRevision'], self.request['merge'])
        self.assertEqual(result['receipt']['sha256'], adapter.release.digest(Path(result['receipt']['path']).read_bytes()))
        operate.assert_not_called()
        evidence = json.loads((self.root / 'evidence/attempt/readback.json').read_bytes())
        self.assertFalse(evidence['physicalAcceptance'])
        path = self.root / 'state/receipts' / (receipt['operationId'] + '.json')
        receipt['outcome'] = 'failed-rolled-back'
        adapter.release.write(path, receipt)
        with mock.patch.object(adapter.runtime_host, 'Host', return_value=host):
            self.assertEqual(adapter.execute(self.config, self.request | {'operation': 'reconcile'})['status'], 'uncertain')

    def test_running_mismatch_missing_health_or_active_barrier_never_claim_installed(self):
        import runtime_adapter as adapter
        host, _, _ = self.installed_fixture()
        with mock.patch.object(adapter.runtime_host, 'Host', return_value=host):
            with mock.patch.object(host, 'running_build', return_value={'sourceRevision': 'b' * 40, 'version': '1.0.0'}):
                self.assertEqual(adapter.execute(self.config, self.request | {'operation': 'reconcile'})['status'], 'uncertain')
            with mock.patch.object(host, 'health', side_effect=ValueError('bounded-health-failure')):
                self.assertEqual(adapter.execute(self.config, self.request | {'operation': 'reconcile'})['status'], 'uncertain')
            adapter.release.write(self.root / 'state/upgrade-records/active.json', {})
            self.assertEqual(adapter.execute(self.config, self.request | {'operation': 'reconcile'})['status'], 'uncertain')

    def test_install_binds_exact_native_plan_deadline_and_retained_receipt(self):
        import runtime_adapter as adapter
        host, receipt, plan = self.installed_fixture()
        observed = []
        def operate(exact, npm, *, deadline, before_stop):
            observed.append((exact, npm, deadline)); before_stop()
            return receipt
        with mock.patch.object(adapter.upgrade, 'plan', return_value=plan) as planner, \
                mock.patch.object(adapter.upgrade, 'operate', side_effect=operate), \
                mock.patch.object(adapter.runtime_host, 'Host', return_value=host):
            result = adapter.execute(self.config, self.request)
        self.assertEqual(result['status'], 'installed')
        planner.assert_called_once_with(self.config['stateDirectory'], self.config['sourceRoot'], self.config['systemdDirectory'], self.request['merge'])
        self.assertEqual(observed, [(plan, self.config['npm'], self.request['deadline'] - 600)])
        self.assertEqual(json.loads((self.root / 'evidence/attempt/plan.json').read_bytes()), plan)

    def test_reserve_rechecked_after_staging_and_never_cancels_admitted_switch(self):
        import runtime_adapter as adapter
        import runtime_host
        from test_runtime_install import FakeHost
        host, _, plan = self.installed_fixture()
        # Exercise the actual native transition's final gate, before durable intent or stop.
        plan['previous'] = adapter.upgrade.selected(self.root / 'state')[1]
        calls = []
        host.calls.clear()
        def expired():
            calls.append('checked'); adapter.reserve(time.time() + 5, 600)
        with self.assertRaises(ValueError):
            adapter.upgrade.transition(plan, self.root / 'candidate', plan['previous'], self.root / 'compatibility',
                                       host, lambda: None, before_stop=expired)
        self.assertEqual(calls, ['checked'])
        self.assertFalse((self.root / 'state/upgrade-records/active.json').exists())
        self.assertNotIn('stop', host.calls)
        with runtime_host.preflight_deadline(time.time() - 1), self.assertRaises(TimeoutError):
            runtime_host.run([sys.executable, '-c', 'pass'])
        self.assertIsNone(runtime_host.PREFLIGHT_DEADLINE.get())

    def test_duplicate_json_authority_and_symlink_configuration_are_rejected(self):
        import runtime_adapter as adapter
        with self.assertRaises(ValueError):
            adapter.strict_json('{"owner":"a","owner":"b"}')
        link = self.root / 'link.json'; link.symlink_to(self.path)
        with self.assertRaises(ValueError):
            adapter.configuration(link)


if __name__ == '__main__':
    unittest.main()
