"""#194: the vendored app verification core is the released app-verify 1.1.0, byte for byte."""
import hashlib
import json
from pathlib import Path
import tarfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = 'jimmie-potts-app-verify-1.1.0.tgz'
SHA256 = '1a0447ec6324f815bc89c3f671207ef452cde120c329b5318fd68711e06a3281'
SOURCE = '917d06f75bfe91dd161024a51c0582b5b7ceccde'


class VendoredCoreTest(unittest.TestCase):
    def test_archive_sidecar_receipt_and_pin_agree(self):
        archive = ROOT / 'vendor' / ARCHIVE
        self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), SHA256)
        self.assertEqual((ROOT / 'vendor' / f'{ARCHIVE}.sha256').read_text(), f'{SHA256}  {ARCHIVE}\n')
        receipt = json.loads((ROOT / 'vendor/app-verify-1.1.0-source-receipt.json').read_text())
        self.assertEqual({key: receipt[key] for key in ('artifact', 'version', 'sourceRevision', 'filename', 'sha256')},
                         {'artifact': '@jimmie-potts/app-verify', 'version': '1.1.0', 'sourceRevision': SOURCE, 'filename': ARCHIVE, 'sha256': SHA256})
        package = json.loads((ROOT / 'package.json').read_text())
        self.assertEqual(package['devDependencies']['@jimmie-potts/app-verify'], f'file:vendor/{ARCHIVE}')
        lock = json.loads((ROOT / 'package-lock.json').read_text())['packages']['node_modules/@jimmie-potts/app-verify']
        self.assertEqual((lock['version'], lock['resolved']), ('1.1.0', f'file:vendor/{ARCHIVE}'))
        self.assertEqual(sorted(path.name for path in (ROOT / 'vendor').glob('*app-verify*')),
                         sorted([ARCHIVE, f'{ARCHIVE}.sha256', 'app-verify-1.1.0-source-receipt.json']), 'one vendored core, and no other version')

    def test_every_archived_file_matches_the_archive_manifest(self):
        with tarfile.open(ROOT / 'vendor' / ARCHIVE) as tar:
            manifest = json.loads(tar.extractfile('package/manifest.json').read())
            self.assertEqual(manifest['version'], '1.1.0')
            self.assertGreater(len(manifest['files']), 0)
            for name, digest in manifest['files'].items():
                with self.subTest(file=name):
                    self.assertEqual(hashlib.sha256(tar.extractfile(f'package/{name}').read()).hexdigest(), digest)


if __name__ == '__main__':
    unittest.main()
