"""Pinned install receipts, independent of the unchanged controller API artifact."""
from functools import lru_cache
import hashlib
import importlib.util
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parent / 'vendor/device-contracts-1.2.0'
ARCHIVE = 'jimmie-potts-device-contracts-1.2.0.tgz'
ARCHIVE_SHA256 = 'f05b326b88833086abf1af596569448e409645486e7bef482f74e9a6998ced7e'
MANIFEST_SHA256 = 'd4358ab7257537fdca5787770b0c2591b4e49639ca7fa553e4187bcbb89b6faa'


def verify(root=ROOT):
    archive = root / ARCHIVE
    if archive.is_symlink() or hashlib.sha256(archive.read_bytes()).hexdigest() != ARCHIVE_SHA256:
        raise ValueError('install-contract-archive-invalid')
    manifest = root / 'package/manifest.json'
    if manifest.is_symlink() or hashlib.sha256(manifest.read_bytes()).hexdigest() != MANIFEST_SHA256:
        raise ValueError('install-contract-manifest-invalid')
    with tarfile.open(archive, 'r:gz') as package:
        if package.extractfile('package/manifest.json').read() != manifest.read_bytes():
            raise ValueError('install-contract-manifest-invalid')
    for name, digest in json.loads(manifest.read_bytes())['files'].items():
        path = root / 'package' / name
        if (Path(name).is_absolute() or '..' in Path(name).parts or path.is_symlink()
                or path.resolve() != path.absolute()
                or hashlib.sha256(path.read_bytes()).hexdigest() != digest):
            raise ValueError('install-contract-file-invalid')
    return root / 'package'


@lru_cache(maxsize=1)
def validator():
    path = verify() / 'python/agent_device_hub_contracts/__init__.py'
    spec = importlib.util.spec_from_file_location('nanoleaf_install_contract_1_2', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate_install_receipt


def validate_receipt(value):
    return validator()(value)
