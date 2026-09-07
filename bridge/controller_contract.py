"""Verified optional shared consumer. Legacy bridge startup never imports this module."""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent / 'vendor/device-contracts-1.0.0'
PACKAGE = ROOT / 'package'
ARCHIVE = 'jimmie-potts-device-contracts-1.0.0.tgz'
SHA256 = '5e0b30ac92e6e8e1e38d8249b740b565de66e3cc810a04bc6fac23e182e84e87'


def verify(root=ROOT):
    if hashlib.sha256((root / ARCHIVE).read_bytes()).hexdigest() != SHA256:
        raise ValueError('Controller contract archive verification failed.')
    # Verify the manifest itself against the immutable archive, then each file.
    import tarfile
    with tarfile.open(root / ARCHIVE, 'r:gz') as archive:
        manifest_bytes = archive.extractfile('package/manifest.json').read()
        if (root / 'package/manifest.json').read_bytes() != manifest_bytes:
            raise ValueError('Controller contract manifest verification failed.')
        manifest = json.loads(manifest_bytes)
        for name, digest in manifest['files'].items():
            path = root / 'package' / name
            if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise ValueError('Controller contract file verification failed.')
    return root / 'package'


def load():
    package = verify()
    spec = importlib.util.spec_from_file_location('nanoleaf_verified_contracts', package / 'python/agent_device_hub_contracts/__init__.py')
    consumer = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(consumer)
    except ImportError as error:
        raise RuntimeError('Install requirements-controller.txt before enabling the controller API.') from error
    return consumer


if __name__ == '__main__':
    verify()
