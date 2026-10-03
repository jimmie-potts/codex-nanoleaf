"""Explicit optional host diagnostics; importing this leaf starts no I/O."""
from contextlib import nullcontext
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tarfile
import uuid

ROOT = Path(__file__).resolve().parent / 'vendor/observability-1.1.0'
ARCHIVE = 'jimmie-potts-bunny-observability-1.1.0.tgz'
SHA256 = '4a75174d42e9454d90e3b2dbc0351b6de653ea6ac6a75e2d710373866f1cba3c'
MANIFEST_SHA256 = 'e1791383ee6830ac4d5cbafc10759844834da2687258c5f4527d495667a744f5'


def verify(root=ROOT):
    if hashlib.sha256((root / ARCHIVE).read_bytes()).hexdigest() != SHA256:
        raise ValueError('Diagnostic archive verification failed.')
    manifest_bytes = (root / 'package/manifest.json').read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != MANIFEST_SHA256:
        raise ValueError('Diagnostic manifest verification failed.')
    with tarfile.open(root / ARCHIVE) as archive:
        if archive.extractfile('package/manifest.json').read() != manifest_bytes:
            raise ValueError('Diagnostic manifest verification failed.')
    for name, digest in json.loads(manifest_bytes)['files'].items():
        path = root / 'package' / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Diagnostic file verification failed.')
    return root / 'package'


@lru_cache(maxsize=1)
def load():
    package = verify()
    name = 'nanoleaf_verified_observability'
    spec = importlib.util.spec_from_file_location(name, package / 'python/bunny_observability/__init__.py')
    consumer = importlib.util.module_from_spec(spec)
    sys.modules[name] = consumer
    try:
        spec.loader.exec_module(consumer)
        runtime = importlib.import_module(name + '.host')
    except Exception:
        sys.modules.pop(name, None)
        raise
    return consumer, runtime.HostDiagnostics


def ticket_fields(value):
    ticket = value.get('requestId', {}) if type(value) is dict else {}
    if type(ticket) is not dict:
        return {}
    return {key: ticket[field] for key, field in
            [('bunny.ticket.epoch', 'epoch'), ('bunny.ticket.sequence', 'sequence')] if field in ticket}


def outcome(value):
    """A transport acknowledgment is not a successful physical effect."""
    if type(value) is not dict:
        return 'rejected'
    if value.get('outcome') == 'partially-applied':
        return 'partial'
    if value.get('outcome') == 'uncertain':
        return 'uncertain'
    if value.get('priorEffects') in ('possible', 'uncertain') or bool(value.get('uncertainOperations')) or value.get('failure', {}).get('code') == 'uncertain-result':
        return 'uncertain'
    return {'queued':'queued', 'sent':'transport-acknowledged', 'failed':'failed',
            'cancelled':'cancelled', 'partial':'partial', 'applied':'succeeded'}.get(value.get('outcome'), 'rejected')


class Diagnostics:
    def __init__(self, host=None, consumer=None, resource=None, tracing=False):
        self.host, self.consumer, self.resource, self.tracing = host, consumer, resource, tracing
        self.enabled = host is not None
        self.closed = False

    def event(self, name, scope='bunny.host', attributes=None, severity='INFO'):
        if not self.enabled or self.closed:
            return False
        try:
            correlation = {}
            if self.tracing:
                from opentelemetry.trace import get_current_span
                identity = get_current_span().get_span_context()
                if identity.is_valid:
                    correlation = dict(trace_id=f'{identity.trace_id:032x}', span_id=f'{identity.span_id:016x}',
                                       trace_flags=f'{int(identity.trace_flags)&1:02x}')
            record = self.consumer.create_record(dict(timestamp=datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z'),
                event_name=name, severity_text=severity, resource=self.resource, scope=dict(name=scope,version='1.0.0'),
                attributes={'bunny.provenance':'source', **(attributes or {})}, **correlation))
            return record['ok'] and self.host.emit(record['value'])
        except Exception:
            return False

    def operation(self, scope, operation, **kwargs):
        return self.host.operation(scope, operation, **kwargs) if self.enabled else nullcontext()

    def receipt(self, value, operation='status'):
        if not self.enabled:
            return
        try:
            result = outcome(value)
            name = {'queued':'command.queued', 'rejected':'command.rejected', 'cancelled':'command.cancelled'}.get(result, 'command.completed')
            self.event(name, 'bunny.controller', {**ticket_fields(value), 'bunny.operation':operation,
                       'bunny.outcome':result}, 'WARN' if result in ('failed','uncertain','rejected') else 'INFO')
        except Exception:
            pass

    def stored_receipt(self, db, table, sequence, operation):
        if self.enabled:
            try:
                row = db.execute('SELECT receipt FROM '+table+' WHERE sequence=?', (sequence,)).fetchone()
                if row:
                    self.receipt(json.loads(row[0]), operation)
            except Exception:
                pass

    def capture_context(self):
        return self.host.capture_context() if self.enabled else None

    def run_context(self, captured):
        return self.host.run_context(captured) if self.enabled else nullcontext()

    def close(self):
        if self.enabled and not self.closed:
            self.event('process.stopped')
            self.closed = True
            self.host.close()

    def counts(self):
        return self.host.counts() if self.enabled else {'enabled':False}

    def __enter__(self):
        return self

    def __exit__(self, kind, value, traceback):
        if kind:
            self.event('process.failed', severity='ERROR')
        self.close()


def start(service, *, environ=None, local_sink=None):
    env = os.environ if environ is None else environ
    if env.get('BUNNY_DIAGNOSTICS') != '1':
        return Diagnostics()
    origin = env.get('BUNNY_OTLP_ORIGIN') or None
    # Detached workers have no local output channel. Require an explicit owned sink.
    if service == 'nanoleaf-worker' and origin is None:
        return Diagnostics()
    try:
        consumer, host_type = load()
        resource = {'service.name':service, 'service.namespace':'bunny', 'service.version':'0.1.0',
                    'service.instance.id':str(uuid.uuid4()), 'deployment.environment.name':'development'}
        tracing = env.get('BUNNY_TRACING') == '1'
        sink = (lambda line: None) if service == 'nanoleaf-worker' and local_sink is None else local_sink
        host = host_type(enabled=True, resource=resource, collector_origin=origin, tracing=tracing,
                         sampling_ratio=0.1, local_sink=sink)
        result = Diagnostics(host, consumer, resource, tracing)
        result.event('process.started')
        return result
    except Exception:
        # Optional diagnostics cannot prevent the existing controller or worker from running.
        return Diagnostics()
