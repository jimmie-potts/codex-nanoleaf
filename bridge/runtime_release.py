"""Nanoleaf release content and durable private records; no service or device effects."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import uuid

COMPONENTS = ('bridge', 'mcp', 'vendor')
SHA = re.compile(r'[0-9a-f]{40}\Z')


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True) + '\n').encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def sync(directory):
    descriptor = os.open(directory, os.O_DIRECTORY | os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def sync_tree(root):
    root = Path(root)
    paths = list(root.rglob('*'))
    for path in paths:
        if path.is_file() and not path.is_symlink():
            with path.open('rb') as source:
                os.fsync(source.fileno())
    for path in sorted((path for path in paths if path.is_dir() and not path.is_symlink()), key=lambda path: len(path.parts), reverse=True):
        sync(path)
    sync(root)


def write(path, value):
    """A failed final fsync is a failed write even if readers can see the new bytes."""
    path = Path(path)
    if path.is_symlink() or not path.parent.is_dir() or path.parent.is_symlink():
        raise ValueError('unsafe-record-path')
    temporary = path.with_name('.' + path.name + '-' + uuid.uuid4().hex)
    try:
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, 'wb') as output:
            output.write(encoded(value))
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        sync(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def inventory(root):
    """Hash the entire owned closure, including modes and safe relative links.

    Bytecode is never shipped or written by managed units (PYTHONDONTWRITEBYTECODE
    is set in the entrypoint). Existing legacy caches are included in its inventory.
    """
    root = Path(root).absolute()
    if root.is_symlink() or not root.is_dir():
        raise ValueError('inventory-root')
    found = {}
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root).as_posix()
        info = path.lstat()
        mode = stat.S_IMODE(info.st_mode)
        if stat.S_ISLNK(info.st_mode):
            target = os.readlink(path)
            if Path(target).is_absolute() or not path.resolve().is_relative_to(root) or not path.exists():
                raise ValueError('escaping-or-broken-link')
            found[relative] = {'kind': 'link', 'target': target}
        elif stat.S_ISDIR(info.st_mode):
            found[relative] = {'kind': 'directory', 'mode': mode}
        elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
            found[relative] = {'kind': 'file', 'mode': mode, 'sha256': digest(path.read_bytes())}
        else:
            raise ValueError('unsupported-inventory-entry')
    return found


def payload(root):
    root = Path(root)
    result = {}
    for name in COMPONENTS:
        path = root / name
        if path.is_symlink() or not path.is_dir():
            raise ValueError('component-link-or-missing')
        result[name] = {'kind': 'directory', 'mode': stat.S_IMODE(path.stat().st_mode)}
        result.update({name + '/' + key: value for key, value in inventory(path).items()})
    return result


def seal(root, revision, version, archive):
    root = Path(root)
    if not SHA.fullmatch(revision) or not isinstance(version, str) or not version:
        raise ValueError('unknown-source-identity')
    manifest = {'format': 1, 'sourceRevision': revision, 'version': version,
                'archiveSha256': digest(archive), 'files': payload(root)}
    identity = dict(kind='release', sourceRevision=revision, version=version,
                    archiveSha256=digest(archive), manifestSha256=digest(encoded(manifest)))
    (root / 'source.tar').write_bytes(archive)
    write(root / 'manifest.json', manifest)
    write(root / 'release.json', identity)
    return identity


def verify(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('release-link')
    if {p.name for p in root.iterdir()} != {*COMPONENTS, 'source.tar', 'manifest.json', 'release.json'}:
        raise ValueError('release-inventory')
    for name in ('manifest.json', 'release.json', 'source.tar'):
        if (root / name).is_symlink():
            raise ValueError('release-metadata-link')
    manifest = json.loads((root / 'manifest.json').read_bytes())
    identity = json.loads((root / 'release.json').read_bytes())
    expected = dict(kind='release', sourceRevision=manifest['sourceRevision'], version=manifest['version'],
                    archiveSha256=digest((root / 'source.tar').read_bytes()),
                    manifestSha256=digest((root / 'manifest.json').read_bytes()))
    if (not SHA.fullmatch(expected['sourceRevision']) or identity != expected or manifest['format'] != 1
            or manifest['archiveSha256'] != expected['archiveSha256'] or manifest['files'] != payload(root)):
        raise ValueError('release-inventory-or-provenance')
    return identity


def build(module_file):
    """Call once at startup; never infer a build from an installation's current link."""
    try:
        identity = verify(Path(module_file).resolve().parent.parent)
        return {key: identity[key] for key in ('sourceRevision', 'version')}
    except (OSError, ValueError, KeyError, TypeError):
        return {'sourceRevision': 'unknown', 'version': 'unknown'}
