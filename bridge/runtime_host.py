"""Bounded Linux effects for the Nanoleaf updater; only named user units and paths."""
import contextlib
from contextvars import ContextVar
import http.client
import json
import os
from pathlib import Path
import shlex
import re
import signal
import sqlite3
import subprocess
import time

import devices
import runtime_release as release

UNITS = tuple('codex-nanoleaf-' + name + '.service' for name in ('wall', 'controller', 'mcp'))
PREFLIGHT_DEADLINE = ContextVar('nanoleaf_preflight_deadline', default=None)


@contextlib.contextmanager
def preflight_deadline(deadline):
    token = PREFLIGHT_DEADLINE.set(deadline)
    try:
        yield
    finally:
        PREFLIGHT_DEADLINE.reset(token)


def bounded_timeout(maximum):
    deadline = PREFLIGHT_DEADLINE.get()
    if deadline is None:
        return maximum
    remaining = deadline - time.time()
    if remaining <= 0:
        raise TimeoutError('preflight-deadline')
    return min(maximum, remaining)


BYPASS = (1 << 1) | (1 << 2)  # CAP_DAC_OVERRIDE and CAP_DAC_READ_SEARCH


def run(arguments, **kwargs):
    return subprocess.run([str(arg) for arg in arguments], check=True, capture_output=True,
                          timeout=bounded_timeout(kwargs.pop('timeout', 30)), **kwargs)


def process(pid):
    """A Linux identity includes start ticks, UID and argv, not just its executable name."""
    try:
        root = Path('/proc') / str(pid)
        status = dict(line.split(':', 1) for line in (root / 'status').read_text().splitlines() if ':' in line)
        stat = (root / 'stat').read_text().rsplit(')', 1)[1].split()
        return {'pid': int(pid), 'startTicks': int(stat[19]), 'state': stat[0],
                'uid': int(status['Uid'].split()[1]), 'capabilities': int(status['CapEff'].strip(), 16),
                'argv': [p.decode() for p in (root / 'cmdline').read_bytes().split(b'\0') if p]}
    except (FileNotFoundError, ProcessLookupError):
        return None


def same_process(left, right):
    return right is not None and all(left[key] == right[key] for key in ('pid', 'startTicks', 'uid', 'argv'))


class Host:
    def __init__(self, directory, units):
        self.directory = Path(directory)
        self.units = Path(units)
        self.deadline = None

    def remaining(self, maximum):
        maximum = bounded_timeout(maximum)
        if self.deadline is None:
            return maximum
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('health-deadline')
        return min(maximum, remaining)

    def service(self, name):
        raw = run(['systemctl', '--user', 'show', name, '--property=ActiveState,SubState,MainPID,FragmentPath,DropInPaths,User,CapabilityBoundingSet,AmbientCapabilities,NeedDaemonReload'], text=True, timeout=self.remaining(30)).stdout
        return dict(line.split('=', 1) for line in raw.splitlines() if '=' in line)

    def snapshot(self):
        result = {}
        config = json.loads((self.directory / 'config.json').read_bytes())
        for name in UNITS:
            observed = self.service(name)
            path = self.units / name
            if (path.is_symlink() or not path.is_file() or observed['FragmentPath'] != str(path)
                    or observed.get('DropInPaths') or observed.get('AmbientCapabilities') or observed.get('NeedDaemonReload') != 'no'
                    or observed.get('User') not in ('', str(os.getuid()))):
                raise ValueError('unsupported-service-ownership')
            lines = path.read_text().splitlines()
            fields, section = {}, None
            allowed = {'Unit': {'Description'}, 'Service': {'Type', 'ExecStart', 'UMask', 'Restart', 'RestartSec'},
                       'Install': {'WantedBy'}}
            for line in lines:
                line = line.strip()
                if not line or line.startswith(('#', ';')):
                    continue
                if line.startswith('[') and line.endswith(']'):
                    section = line[1:-1]
                    if section not in allowed:
                        raise ValueError('unsupported-service-effects')
                    continue
                key, separator, value = line.partition('=')
                if not separator or section not in allowed or key not in allowed[section] or (section, key) in fields:
                    raise ValueError('unsupported-service-effects')
                fields[section, key] = value
            fixed = {('Service', 'Type'): 'simple', ('Service', 'UMask'): '0077',
                     ('Service', 'Restart'): 'on-failure', ('Service', 'RestartSec'): '2',
                     ('Install', 'WantedBy'): 'default.target'}
            if any(fields.get(key) != value for key, value in fixed.items()):
                raise ValueError('unsupported-service-effects')
            commands = [line[len('ExecStart='):] for line in lines if line.startswith('ExecStart=')]
            if len(commands) != 1:
                raise ValueError('unsupported-service-command')
            argv = shlex.split(commands[0])
            component = 'mcp' if name.endswith('-mcp.service') else 'bridge'
            expected = str(self.directory / 'runtime' / component / ('dist/main.js' if component == 'mcp' else 'bridge.py'))
            executable = str(self.directory / ('runtime/node/bin/node' if component == 'mcp' else '.venv/bin/python'))
            if component == 'mcp':
                required = [executable, expected, '--config', str(self.directory / 'mcp-config.json')]
            else:
                controller = name.endswith('-controller.service')
                required = [executable, expected, 'controller-serve' if controller else 'serve',
                            '--state-dir', str(self.directory), '--port', str(config['controller_port' if controller else 'wall_port'])]
            if argv != required:
                raise ValueError('unsupported-service-command')
            pid = int(observed['MainPID'])
            running = process(pid) if pid else None
            if running and (running['uid'] != os.getuid() or running['capabilities'] & BYPASS):
                raise ValueError('privileged-service-cannot-be-fenced')
            if running and running['argv'] != required:
                raise ValueError('unsupported-service-command')
            result[name] = {'sha256': release.digest(path.read_bytes()), 'argv': argv,
                            'active': observed['ActiveState'], 'process': running}
        return result

    def owned_processes(self, roots):
        result = []
        for entry in Path('/proc').iterdir():
            if not entry.name.isdigit() or int(entry.name) == os.getpid():
                continue
            info = process(int(entry.name))
            if not info or info['state'] == 'Z':
                continue
            # Only supported argv-based bridge/MCP entrypoints. No name-based pkill.
            argv = info['argv']
            executable = Path(argv[0]).name if argv else ''
            if executable not in {'python', 'python3', 'python3.12', 'python3.14', 'node'}:
                continue
            arguments = argv[1:]
            while arguments and arguments[0] in ('-B', '-u', '-I', '-E', '-s', '-S', '-q'):
                arguments = arguments[1:]
            script = arguments[0] if arguments else ''
            if script and not script.startswith('-') and not Path(script).is_absolute():
                try:
                    script = os.path.normpath(str(Path(os.readlink(entry / 'cwd')) / script))
                except FileNotFoundError:
                    continue
                except PermissionError:
                    if info['uid'] != os.getuid():
                        continue
                    raise ValueError('owned-process-entrypoint-unreadable') from None
            matched = (executable in {'python', 'python3', 'python3.12', 'python3.14', 'node'}
                       and any(script.startswith(str(root) + '/') for root in roots)
                       and (script.endswith('/bridge.py') or script.endswith('/dist/main.js')))
            if matched:
                if info['uid'] != os.getuid() or info['capabilities'] & BYPASS:
                    raise ValueError('privileged-or-foreign-owned-writer')
                result.append(info)
        return sorted(result, key=lambda info: info['pid'])

    def qualify(self, roots):
        own = process(os.getpid())
        if not own or own['uid'] == 0 or own['capabilities'] & BYPASS:
            raise ValueError('installer-permission-bypass')
        self.snapshot()
        for path in (self.directory / '.venv/bin/python', self.directory / 'runtime/node/bin/node'):
            actual = path.resolve(strict=True)
            if actual.stat().st_mode & 0o6000 or 'security.capability' in os.listxattr(actual):
                raise ValueError('privileged-runtime-executable')
        return self.owned_processes(roots)

    def running_build(self, services):
        if services[UNITS[1]]['active'] != 'active' or not services[UNITS[1]]['process']:
            return None
        try:
            config = json.loads((self.directory / 'config.json').read_bytes())
            credentials = json.loads((self.directory / 'mcp-credentials.json').read_bytes())
            principal = next(p for p in credentials['principals'] if 'read' in p['scopes'])
            raw, _ = self.http(config['controller_port'], '/controller/meta/v1/health', principal['upstreamToken'])
            build = json.loads(raw)['build']
            if set(build) != {'sourceRevision', 'version'} or not isinstance(build['version'], str):
                raise ValueError('invalid-running-build')
            if build['sourceRevision'] != 'unknown' and not release.SHA.fullmatch(build['sourceRevision']):
                raise ValueError('invalid-running-build')
            return build
        except (OSError, ValueError, KeyError, StopIteration):
            return {'sourceRevision': 'unknown', 'version': 'unknown'}

    def stop(self, roots):
        run(['systemctl', '--user', 'stop', *UNITS], timeout=45)
        deadline = time.monotonic() + 10
        quiet = 0
        while time.monotonic() < deadline:
            remaining = self.owned_processes(roots)
            if not remaining:
                quiet += 1
                if quiet >= 2:
                    if any(self.service(name)['ActiveState'] not in ('inactive', 'failed') for name in UNITS):
                        raise ValueError('service-stop-unverified')
                    return
            else:
                quiet = 0
                for info in remaining:
                    # pidfd binds the signal to this task even if the numeric PID is reused.
                    try:
                        descriptor = os.pidfd_open(info['pid'])
                    except ProcessLookupError:
                        continue
                    try:
                        if same_process(info, process(info['pid'])):
                            signal.pidfd_send_signal(descriptor, signal.SIGTERM)
                    finally:
                        os.close(descriptor)
            time.sleep(0.05)
        raise ValueError('writer-stop-timeout')

    def start(self):
        run(['systemctl', '--user', 'start', *UNITS], timeout=45)

    @contextlib.contextmanager
    def worker_locks(self):
        config = json.loads((self.directory / 'config.json').read_bytes())
        with contextlib.ExitStack() as stack:
            for device in devices.registry(config):
                path = self.directory / devices.lock_file(device)
                if path.is_symlink():
                    raise ValueError('worker-lock-link')
                connection = sqlite3.connect(path, timeout=0.25)
                stack.callback(connection.close)
                connection.execute('BEGIN EXCLUSIVE')
            yield

    def http(self, port, path, token=None, body=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=self.remaining(2))
        fields = {} if token is None else {'Authorization': 'Bearer ' + token}
        fields.update(headers or {})
        raw = None if body is None else json.dumps(body)
        if raw is not None:
            fields['Content-Type'] = 'application/json'
        try:
            connection.request('GET' if raw is None else 'POST', path, raw, fields)
            response = connection.getresponse()
            content = response.read(2_000_001)
            if response.status not in (200, 202) or len(content) > 2_000_000:
                raise ValueError('health-http')
            return content, dict(response.getheaders())
        finally:
            connection.close()

    def health(self, identity, selected, started_after):
        """Read-only loopback checks: no MCP tool call, controller command or device request."""
        config = json.loads((self.directory / 'config.json').read_bytes())
        credentials = json.loads((self.directory / 'mcp-credentials.json').read_bytes())
        principal = next(p for p in credentials['principals'] if 'read' in p['scopes'])
        bearer = (self.directory / 'mcp-client-token').read_text().strip()
        last = None
        self.deadline = time.monotonic() + 45
        for _ in range(20):
            try:
                observed = self.snapshot()
                for unit in observed.values():
                    info = unit['process']
                    if unit['active'] != 'active' or not info or info['startTicks'] < started_after:
                        raise ValueError('running-process-identity')
                roots = [self.directory / 'runtime' / part for part in ('bridge', 'mcp')]
                roots += [Path(selected) / part for part in ('bridge', 'mcp')]
                processes = self.owned_processes(roots)
                if any(info['startTicks'] < started_after for info in processes):
                    raise ValueError('old-bridge-process')
                page, _ = self.http(config['wall_port'], '/')
                state, _ = self.http(config['wall_port'], '/api/state')
                json.loads(state)
                template = (Path(selected) / 'bridge/wall.html').read_bytes()
                normalized = re.sub(rb"const token='[A-Za-z0-9_-]+'", b"const token='__CSRF__'", page)
                if not page or template != normalized:
                    raise ValueError('wall-served-artifact')
                if identity['kind'] == 'release':
                    data, _ = self.http(config['controller_port'], '/controller/meta/v1/health', principal['upstreamToken'])
                    body = json.loads(data)
                    if body != {'apiVersion': '1.0', 'serviceHealth': 'ready', 'build': {key: identity[key] for key in ('sourceRevision', 'version')}}:
                        raise ValueError('controller-build-mismatch')
                data, _ = self.http(config['controller_port'], '/controller/v1/devices', principal['upstreamToken'])
                if not json.loads(data).get('devices'):
                    raise ValueError('controller-health')
                headers = {'Accept': 'application/json, text/event-stream'}
                data, reply = self.http(config['mcp_port'], '/mcp', bearer, {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-11-25', 'capabilities': {}, 'clientInfo': {'name': 'nanoleaf-upgrade', 'version': '1'}}}, headers)
                if 'result' not in json.loads(data):
                    raise ValueError('mcp-initialize')
                session = next((v for k, v in reply.items() if k.lower() == 'mcp-session-id'), None)
                if not session:
                    raise ValueError('mcp-session')
                headers.update({'Mcp-Session-Id': session, 'MCP-Protocol-Version': '2025-11-25'})
                self.http(config['mcp_port'], '/mcp', bearer, {'jsonrpc': '2.0', 'method': 'notifications/initialized'}, headers)
                data, _ = self.http(config['mcp_port'], '/mcp', bearer, {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list', 'params': {}}, headers)
                if 'nanoleaf_status' not in [tool['name'] for tool in json.loads(data)['result']['tools']]:
                    raise ValueError('mcp-discovery')
                self.deadline = None
                return {'processes': processes, 'units': observed, 'wallSha256': release.digest(page),
                        'controller': 'ready', 'mcp': 'authenticated-discovery'}
            except (OSError, ValueError, KeyError, StopIteration, subprocess.SubprocessError) as error:
                last = error
                if time.monotonic() >= self.deadline:
                    break
                time.sleep(0.25)
        self.deadline = None
        raise ValueError('bounded-health-failure') from last


def ticks():
    return int(float(Path('/proc/uptime').read_text().split()[0]) * os.sysconf('SC_CLK_TCK'))
