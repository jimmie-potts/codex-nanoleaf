"""One bounded controller exchange. No bridge state or device access."""
import http.client
import json
import math
import os
import re
import sys
import threading

MAX_INPUT = 65536
MAX_RESPONSE = 524288


def parse(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate key')
            result[key] = value
        return result
    result = json.loads(text, object_pairs_hook=pairs,
                        parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Invalid number')))
    pending = [(result, 0)]
    while pending:
        value, depth = pending.pop()
        if depth > 32 or isinstance(value, float) and not math.isfinite(value):
            raise ValueError('JSON limit')
        if isinstance(value, (dict, list)):
            pending.extend((child, depth + 1) for child in (value.values() if isinstance(value, dict) else value))
    return result


def validate(value):
    if not isinstance(value, dict):
        raise ValueError('Invalid request')
    operation = value.get('operation')
    keys = {'operation', 'port', 'deviceId', 'token'} | ({'request'} if operation == 'command' else set())
    if set(value) != keys or operation not in ('snapshot', 'command'):
        raise ValueError('Invalid request')
    if type(value['port']) is not int or not 1024 <= value['port'] <= 65535:
        raise ValueError('Invalid port')
    if not isinstance(value['deviceId'], str) or not re.fullmatch(r'[A-Za-z0-9._-]{1,128}', value['deviceId']):
        raise ValueError('Invalid target')
    if not isinstance(value['token'], str) or not re.fullmatch(r'[A-Za-z0-9_-]{43,512}', value['token']):
        raise ValueError('Invalid credential')
    if operation == 'command':
        request = value['request']
        if not isinstance(request, dict) or set(request) != {'apiVersion', 'controllerId', 'deviceId', 'requestId', 'expectedConfigurationRevision', 'expectedGeneration', 'command'}:
            raise ValueError('Invalid command')
        if request['apiVersion'] != '1.0' or request['deviceId'] != value['deviceId'] or not isinstance(request['controllerId'], str) or not re.fullmatch(r'[A-Za-z0-9._-]{1,128}', request['controllerId']):
            raise ValueError('Invalid identity')
        revision = request['expectedConfigurationRevision']
        if type(revision) is not int or not 0 <= revision <= 9007199254740991:
            raise ValueError('Invalid revision')
        for ticket in (request['requestId'], request['expectedGeneration']):
            if not isinstance(ticket, dict) or set(ticket) != {'epoch', 'sequence'} or not isinstance(ticket['epoch'], str) or not re.fullmatch(r'[A-Za-z0-9._-]{1,128}', ticket['epoch']) or type(ticket['sequence']) is not int or not 0 <= ticket['sequence'] <= 9007199254740991:
                raise ValueError('Invalid ticket')
        command = request['command']
        if not isinstance(command, dict) or set(command) != {'kind', 'mode'} or command['kind'] != 'mode.set' or command['mode'] not in ('Work', 'Quiet', 'Free'):
            raise ValueError('Unsupported command')
    return value


def exchange(value):
    validate(value)
    command = value['operation'] == 'command'
    body = json.dumps(value['request'], separators=(',', ':'), allow_nan=False).encode() if command else None
    if body is not None and len(body) > MAX_INPUT:
        raise ValueError('Body limit')
    connection = http.client.HTTPConnection('127.0.0.1', value['port'], timeout=5)
    try:
        headers = {'Host': '127.0.0.1:' + str(value['port']), 'Authorization': 'Bearer ' + value['token']}
        if command:
            headers['Content-Type'] = 'application/json'
        path = '/controller/v1/commands' if command else '/controller/v1/snapshot?deviceId=' + value['deviceId']
        connection.request('POST' if command else 'GET', path, body=body, headers=headers)
        response = connection.getresponse()
        if not 200 <= response.status < 600 or 300 <= response.status < 400:
            raise ValueError('Invalid response')
        data = response.read(MAX_RESPONSE + 1)
        if len(data) > MAX_RESPONSE:
            raise ValueError('Response limit')
        return {'status': response.status, 'body': parse(data.decode('utf-8'))}
    finally:
        connection.close()


def main():
    # Includes stdin and trickle-response time. The parent also bounds the child.
    watchdog = threading.Timer(6, lambda: os._exit(1))
    watchdog.daemon = True
    watchdog.start()
    try:
        raw = sys.stdin.buffer.read(MAX_INPUT + 1)
        if len(raw) > MAX_INPUT:
            raise ValueError('Input limit')
        result = exchange(validate(parse(raw.decode('utf-8'))))
        output = json.dumps(result, separators=(',', ':'), allow_nan=False).encode('utf-8')
        if len(output) > MAX_RESPONSE + 128:
            raise ValueError('Output limit')
        sys.stdout.buffer.write(output)
        sys.stdout.buffer.flush()
        return 0
    except Exception:
        print('Controller exchange unavailable.', file=sys.stderr)
        return 1
    finally:
        watchdog.cancel()


if __name__ == '__main__':
    raise SystemExit(main())
