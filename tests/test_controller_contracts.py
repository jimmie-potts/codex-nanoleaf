"""The installed consumer verifies the delivered artifact before importing it."""
import copy
import importlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from test_bridge import b


class ContractTest(unittest.TestCase):
    def test_verified_import_and_all_shared_cases(self):
        loader = importlib.import_module('controller_contract')
        contract = loader.load()
        cases = json.loads((loader.PACKAGE / 'fixtures/controller-v1.json').read_text())
        self.assertTrue(cases)
        self.assertEqual(len(cases['schemaCases']) + len(cases['semanticCases']), 220)
        for case in cases['schemaCases']:
            with self.subTest(case=case['id']):
                self.assertEqual(contract.validate(case['definition'], case['value']), case['valid'])
        for case in cases['semanticCases']:
            with self.subTest(case=case['id']):
                self.assertEqual(contract.evaluate(copy.deepcopy(case['input'])), case['expected'])

    def test_altered_artifact_rejected(self):
        loader = importlib.import_module('controller_contract')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'contracts'
            shutil.copytree(loader.ROOT, root)
            (root / loader.ARCHIVE).write_bytes(b'altered')
            with self.assertRaises(ValueError): loader.verify(root)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'contracts'
            shutil.copytree(loader.ROOT, root)
            (root / 'package/python/agent_device_hub_contracts/__init__.py').write_text('# changed')
            with self.assertRaises(ValueError): loader.verify(root)

    def test_legacy_import_without_site_packages(self):
        result = subprocess.run([sys.executable, '-S', str(Path(b.__file__)), '--help'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
