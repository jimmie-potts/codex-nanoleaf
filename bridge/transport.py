"""Requests to a Nanoleaf controller's local API. Callers decide what a request means."""
import ipaddress
import json
import urllib.request


def light_request(config, method, endpoint='', payload=None):
    ip = ipaddress.ip_address(config['ip'])
    if ip.version != 4 or not ip.is_private:
        raise ValueError('Use a private IPv4 address for the lights.')
    token = config['token']
    if not token or not token.isalnum():
        raise ValueError('The token must contain only letters and numbers.')
    url = f'http://{ip}:16021/api/v1/{token}{endpoint}'
    body = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(url, data=body, method=method,
                                     headers={'Content-Type': 'application/json'})
    # Keep local-device traffic off configured HTTP proxies.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=1.2) as response:
        data = response.read()
        return json.loads(data) if data else None
