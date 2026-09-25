"""Enroll NL22 Light Panels beside the original Lines device, change their address, or remove them again."""
import argparse
import contextlib
import getpass
import ipaddress
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys
import time
import urllib.error
import urllib.request
import warnings

import devices

KIND = 'panels'
MODEL = 'NL22'
REMOVE_WAIT_SECONDS = 10.0


class Partial(Exception):
    """A failure after the first state write; rerunning the same command finishes the change."""


def read_token(path):
    """A credential from a private token-only file, or a hidden prompt that never echoes."""
    if path is None:
        with warnings.catch_warnings():
            warnings.simplefilter('error', getpass.GetPassWarning)
            try:
                return getpass.getpass('Nanoleaf auth_token (hidden): ').strip()
            except getpass.GetPassWarning:
                raise ValueError('A hidden prompt is unavailable. Use a private --token-file.') from None
    descriptor = os.open(Path(path).expanduser(), os.O_RDONLY | os.O_NONBLOCK)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError('The token file must be a regular private text file.')
        value = os.read(descriptor, 1025)
        if len(value) > 1024:
            raise ValueError('The token file exceeds 1024 bytes.')
        try:
            return value.decode('ascii').strip()
        except UnicodeDecodeError:
            raise ValueError('The token file must contain only ASCII text.') from None
    finally:
        os.close(descriptor)


def private_address(ip):
    address = ipaddress.ip_address(ip)
    if address.version != 4 or not address.is_private:
        raise ValueError('Use a private IPv4 address for the lights.')
    return str(address)


def pair(ip):
    """Ask the device for a new credential while its pairing window is open."""
    url = f'http://{private_address(ip)}:16021/api/v1/new'
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(urllib.request.Request(url, method='POST'), timeout=5) as response:
            token = json.loads(response.read()).get('auth_token')
    except urllib.error.HTTPError as error:
        error.close()
        if error.code == 403:
            raise ValueError('The device refused pairing. Hold its power button until the lights flash, '
                             'then retry within 30 seconds.') from None
        raise
    if not isinstance(token, str):
        raise ValueError('The device did not return a credential.')
    return token


def state_directory(directory):
    # Resolve symlinks first, as the installer does, so a link cannot reach a Windows drive.
    resolved = Path(directory).expanduser().resolve()
    if os.name == 'nt' or re.match(r'^/mnt/[a-zA-Z](?:/|$)', str(resolved)):
        raise ValueError('Only Linux state outside Windows-mounted drives is supported')
    return resolved


def device_id(device):
    if device == devices.DEFAULT:
        raise ValueError('The Lines id `wall` is reserved.')
    if not isinstance(device, str) or not devices.ID.fullmatch(device):
        raise ValueError('Invalid device id. Use 1 to 128 letters, digits, dots, underscores or hyphens.')
    return device


@contextlib.contextmanager
def exclusive(path, timeout=5):
    with contextlib.closing(sqlite3.connect(path, timeout=timeout)) as lock:
        lock.execute('BEGIN EXCLUSIVE')
        yield
        lock.rollback()


def worker_lock(directory, device, wait=0.0, sleep=time.sleep):
    """Hold the device's worker lock, so no instance for it runs; None if one is still running."""
    deadline = time.monotonic() + wait
    while True:
        lock = sqlite3.connect(directory / devices.lock_file(device), timeout=0)
        try:
            lock.execute('BEGIN EXCLUSIVE')
            return lock
        except sqlite3.OperationalError as error:
            lock.close()
            if error.sqlite_errorcode != sqlite3.SQLITE_BUSY:
                raise
        if time.monotonic() >= deadline:
            return None
        sleep(0.1)


def read_config(directory):
    config = json.loads((directory / 'config.json').read_text())
    devices.registry(config)  # A malformed registry is refused, never repaired.
    return config


def check_layout(directory):
    """Refuse a malformed layout file before anything is written, since a rerun could not repair it."""
    path = directory / 'layout.json'
    try:
        if path.exists():
            devices.layout_devices(json.loads(path.read_text()))
    except ValueError as error:
        raise ValueError(f'The saved layout.json is invalid ({str(error).rstrip(".")}). '
                         'Repair it before enrolling or removing a device.') from None


def purge(directory, b, device):
    """Delete a device's rows, meta keys, layout entry and saved scene; shared tasks stay."""
    with contextlib.closing(b.connect_state(directory)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        for table in devices.SCHEMAS:
            db.execute('DELETE FROM ' + table + ' WHERE device=?', (device,))
        suffix = '@' + device
        db.execute('DELETE FROM meta WHERE substr(key, -?) = ?', (len(suffix), suffix))
    devices.save_device_layout(directory / 'layout.json', device, None, b.write_json)
    (directory / devices.scene_file(device)).unlink(missing_ok=True)


def check_target(config, device, ip):
    """The existing entry for a repeat, or None; refuses anything that would redirect an identity."""
    registry = devices.registry(config)
    existing = registry.get(device)
    if existing and (existing['kind'] != KIND or existing['ip'] != ip):
        raise ValueError(f'Device `{device}` is registered at another address or as another kind. '
                         'Move registered Panels with device-address, or remove the device first; '
                         'enrollment never redirects an identity.')
    key = existing['token_ref'] if existing else 'token@' + device
    for other, entry in registry.items():
        if other == device:
            continue
        if entry['ip'] == ip:
            raise ValueError(f'Device `{other}` already uses that address.')
        if entry['token_ref'] == key:
            raise ValueError(f'Device `{device}` shares a credential key with `{other}`. Remove it first.')
    return existing


def check(directory, device, ip):
    """Refuse a conflicting target before a credential is requested from the operator or device."""
    directory = state_directory(directory)
    with exclusive(directory / 'registry-lock.sqlite'):
        check_target(read_config(directory), device_id(device), private_address(ip))


def enroll(directory, b, *, ip, token, device=KIND, request=None):
    """Verify an NL22 device and register it in Free; nothing is written unless every check passes."""
    directory = state_directory(directory)
    device = device_id(device)
    ip = private_address(ip)
    if not token or not token.isascii() or not token.isalnum():
        raise ValueError('The device credential must contain only ASCII letters and numbers.')
    with exclusive(directory / 'registry-lock.sqlite'):
        config = read_config(directory)
        existing = check_target(config, device, ip)
        info = (request or b.light_request)({'ip': ip, 'token': token}, 'GET')
        if not isinstance(info, dict) or info.get('model') != MODEL:
            raise ValueError('The device at that address is not NL22 Light Panels.')
        import panels
        layout = panels.read_layout(info.get('panelLayout'))
        token_ref = 'token@' + device
        if existing:
            # A repeat replaces only the credential; layout, mode and reservations stay.
            config[existing['token_ref']] = token
            b.write_json(directory / 'config.json', config)
        else:
            check_layout(directory)
            lock = worker_lock(directory, device)
            if lock is None:
                raise ValueError(f'A worker for `{device}` is still running. Retry in a moment.')
            try:
                with contextlib.closing(lock):
                    purge(directory, b, device)
                    with contextlib.closing(b.connect_state(directory)) as db, db:
                        # No revision keys: revision and applied both read 0, so nothing is pending.
                        db.execute('INSERT INTO meta VALUES (?, ?)', (devices.meta_key('mode', device), 'free'))
                    devices.save_device_layout(directory / 'layout.json', device, layout, b.write_json)
                config.setdefault('devices', {})[device] = {'kind': KIND, 'ip': ip, 'token_ref': token_ref}
                config[token_ref] = token
                # The registry is written last, so an earlier failure leaves only unread state for an unregistered id.
                b.write_json(directory / 'config.json', config)
            except Exception as error:
                raise Partial() from error
    return {'device': device, 'triangles': len(layout['elements']), 'repeat': bool(existing),
            'firmware': info.get('firmwareVersion')}


def change_address(directory, b, device, ip, *, request=None):
    """Move a registered Panels device to a verified new address; its identity and saved state stay."""
    directory = state_directory(directory)
    if device == devices.DEFAULT:
        raise ValueError('device-address moves Light Panels only; it does not move the Lines device `wall`.')
    device = device_id(device)
    ip = private_address(ip)
    with exclusive(directory / 'registry-lock.sqlite'):
        config = read_config(directory)
        check_layout(directory)
        registry = devices.registry(config)
        entry = registry.get(device)
        if entry is None:
            raise ValueError('Unknown device.')
        if entry['kind'] != KIND:
            raise ValueError(f'Device `{device}` is not Light Panels.')
        if entry['ip'] == ip:
            raise ValueError(f'Device `{device}` is already registered at that address.')
        for other, registered in registry.items():
            if other != device and registered['ip'] == ip:
                raise ValueError(f'Device `{other}` already uses that address.')
        saved = devices.layout_devices(json.loads((directory / 'layout.json').read_text())
                                       if (directory / 'layout.json').exists() else {}).get(device)
        if saved is None or saved['kind'] != KIND:
            raise ValueError(f'Device `{device}` has no saved layout. Remove it and enroll it again.')
        token = devices.credential(config, entry)
        if not token:
            raise ValueError(f'Device `{device}` has no stored credential. Remove it and enroll it again.')
        # One read with the stored credential; no light write reaches the device.
        info = (request or b.light_request)({'ip': ip, 'token': token}, 'GET')
        if not isinstance(info, dict) or info.get('model') != MODEL:
            raise ValueError('The device at that address is not NL22 Light Panels.')
        import panels
        reported = panels.read_layout(info.get('panelLayout'))
        # The same physical set: equal triangles, positions and neighbors, not just an equal count.
        if (reported['elements'] != saved['elements']
                or reported['panel_geometry'] != saved.get('panel_geometry')):
            raise ValueError('The triangles at that address do not match the saved layout. '
                             'Check the address, or remove the device and enroll it again.')
        # Only the registry changes; a running worker reads the address again on its next pass.
        config['devices'][device]['ip'] = ip
        b.write_json(directory / 'config.json', config)
    return {'device': device, 'ip': ip, 'triangles': len(saved['elements'])}


def remove(directory, b, device, *, force=False, wait=REMOVE_WAIT_SECONDS, sleep=time.sleep):
    """Unregister a device, stop its worker and delete what it owned; Lines and shared tasks stay."""
    directory = state_directory(directory)
    device = device_id(device)
    with exclusive(directory / 'registry-lock.sqlite'):
        config = read_config(directory)
        check_layout(directory)
        entry = (config.get('devices') or {}).get(device)
        if entry is not None:
            with contextlib.closing(b.connect_state(directory)) as db:
                control = b.control_state(db, device)
            if not force and control['mode'] != 'free':
                raise ValueError(f'Hand the device back first: run `mode free --device {device}`, '
                                 'wait until status shows nothing pending, then remove it.')
            if not force and control['revision'] != control['applied']:
                raise ValueError('Free has not been applied yet. Wait until status shows nothing pending, '
                                 'or add --force if the device is unreachable.')
            del config['devices'][device]
            if entry['token_ref'] != 'token' and all(other['token_ref'] != entry['token_ref']
                                                     for other in config['devices'].values()):
                config.pop(entry['token_ref'], None)
            b.write_json(directory / 'config.json', config)
        elif not leftovers(directory, b, device):
            raise ValueError('Unknown device.')
        try:
            if entry is not None:
                with contextlib.closing(b.connect_state(directory)) as db, db:
                    b.mark_dirty(db)  # A waiting instance wakes, sees the device is gone and exits.
            lock = worker_lock(directory, device, wait, sleep)
            if lock is None:
                return {'device': device, 'cleaned': False}
            with contextlib.closing(lock):
                purge(directory, b, device)
        except Exception as error:
            raise Partial() from error
    return {'device': device, 'cleaned': True}


def leftovers(directory, b, device):
    if (directory / devices.scene_file(device)).exists():
        return True
    layout = directory / 'layout.json'
    if layout.exists() and device in devices.layout_devices(json.loads(layout.read_text())):
        return True
    suffix = '@' + device
    with contextlib.closing(b.connect_state(directory)) as db:
        if db.execute('SELECT 1 FROM meta WHERE substr(key, -?) = ?', (len(suffix), suffix)).fetchone():
            return True
        return any(db.execute('SELECT 1 FROM ' + table + ' WHERE device=? LIMIT 1', (device,)).fetchone()
                   for table in devices.SCHEMAS)


def reason(error, action):
    """An operator message that never repeats device responses or credentials."""
    if isinstance(error, sqlite3.Error):
        return 'the saved state is busy; retry in a moment'
    if isinstance(error, ValueError):
        return str(error).rstrip('.')
    if action == 'Device removal':
        return 'the saved state could not be read or written'
    return 'the device or saved state could not be reached'


def command(argv, b):
    parser = argparse.ArgumentParser(prog='nanoleaf ' + argv[0], description=__doc__)
    parser.add_argument('--state-dir', type=Path, help=argparse.SUPPRESS)
    if argv[0] == 'device-enroll':
        parser.add_argument('--ip', required=True, help='Private IPv4 address of the NL22 Light Panels.')
        parser.add_argument('--device', default=KIND, help='Stable id for the new device; defaults to panels.')
        source = parser.add_mutually_exclusive_group()
        source.add_argument('--token-file', type=Path, help='Private token-only file; otherwise use a hidden prompt.')
        source.add_argument('--pair', action='store_true',
                            help="Obtain a credential from the device's pairing window.")
    elif argv[0] == 'device-address':
        parser.add_argument('--device', required=True, help='Registered Light Panels id to move.')
        parser.add_argument('--ip', required=True, help='New private IPv4 address of the same device.')
    elif argv[0] == 'device-remove':
        parser.add_argument('--device', required=True, help='Registered device id to remove.')
        parser.add_argument('--force', action='store_true',
                            help='Remove an unreachable device whose Free handoff cannot finish.')
    else:
        parser.error('Use device-enroll, device-address or device-remove.')
    args = parser.parse_args(argv[1:])
    action = {'device-remove': 'Device removal', 'device-address': 'Address change'}.get(argv[0], 'Device enrollment')
    directory = args.state_dir or b.data_dir()
    try:
        if argv[0] == 'device-remove':
            result = remove(directory, b, args.device, force=args.force)
            if result['cleaned']:
                print(f'Removed `{result["device"]}`. Lines and shared tasks are unchanged.')
            else:
                print(f'Removed the `{result["device"]}` registration, but its worker is still stopping. '
                      f'Run `device-remove --device {result["device"]}` again to finish removing its saved state.')
            return 0
        if argv[0] == 'device-address':
            result = change_address(directory, b, args.device, args.ip)
            print(f'Moved `{result["device"]}` to {result["ip"]} after checking its {result["triangles"]} triangles. '
                  'Its mode, layout, reservations and scene are unchanged.')
            print('No service restart is needed: its worker sends to the new address from its next pass.')
            return 0
        check(directory, args.device, args.ip)
        if args.pair:
            print("Hold the Light Panels' power button for 5 to 7 seconds until the lights flash, "
                  'then press Enter within 30 seconds.')
            sys.stdin.readline()
            token = pair(args.ip)
        else:
            token = read_token(args.token_file)
        result = enroll(directory, b, ip=args.ip, token=token, device=args.device)
    except Partial as error:
        print(f'{action} stopped after changing saved state: {reason(error.__cause__, action)}. '
              'Lines and shared tasks are unchanged; run the same command again to finish.', file=sys.stderr)
        return 1
    except urllib.error.HTTPError as error:
        error.close()
        print(f'{action}: the device answered HTTP {error.code}. Nothing was changed.', file=sys.stderr)
        return 1
    except (ValueError, OSError, sqlite3.Error) as error:
        print(f'{action}: {reason(error, action)}. Nothing was changed.', file=sys.stderr)
        return 1
    device = result['device']
    if result['repeat']:
        print(f'Updated the credential for `{device}`. Its mode, layout and reservations are unchanged.')
    else:
        print(f'Enrolled NL22 Light Panels as `{device}` with {result["triangles"]} triangles '
              f'(firmware {result["firmware"] or "unknown"}).')
        print('It starts in Free and receives nothing until you choose Work or Quiet:')
        print(f'  nanoleaf mode work --device {device}')
    print('No service restart is needed: hooks and the worker read the device list each time they start, '
          'and the wall map, controller and MCP stay on Lines.')
    return 0
