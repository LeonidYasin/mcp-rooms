"""Operator-root read-only Caddy inspection. Private snapshot, sanitized stdout only."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from urllib.request import build_opener, HTTPRedirectHandler, Request

HOST = 'leonid-mcp.duckdns.org'
PREFIX = '/rooms-test'
MAX_CONFIG_BYTES = 4 * 1024 * 1024
MAX_NODES = 100
UNITS = ('mcp-server.service', 'mcp-test.service', 'caddy.service', 'mcp-rooms-test.service')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def command(args):
    return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL, timeout=20).strip()


def service(unit):
    raw = command(['systemctl', 'show', unit, '--no-pager',
                   '--property=LoadState,ActiveState,SubState,MainPID,User,WorkingDirectory,RuntimeMaxUSec,ActiveEnterTimestampMonotonic'])
    return dict(line.split('=', 1) for line in raw.splitlines() if '=' in line)


def safe_path(value):
    if isinstance(value, str) and re.fullmatch(r'/(?:mcp|test|test-rooms-b|rooms-test)(?:/mcp|/signup|/signup\.js|/register|/identity|/credentials(?:/current)?|/\*)?/?', value):
        return value
    return '<other-path>'


def upstreams(values):
    ports = set(); other = False
    for item in values if isinstance(values, list) else []:
        dial = item.get('dial', '') if isinstance(item, dict) else ''
        match = re.fullmatch(r'(?:127\.0\.0\.1|localhost|\[::1\]):([0-9]{1,5})', dial) if isinstance(dial, str) else None
        if match:
            ports.add(int(match[1]))
        else:
            other = True
    return sorted(ports), other


def summarize(config):
    servers = config.get('apps', {}).get('http', {}).get('servers', {})
    output = []; expected_servers = set(); prefix_found = False; visited = 0
    def walk(node, location, server_index):
        nonlocal prefix_found, visited
        visited += 1
        if visited > 10000:
            raise ValueError('configuration_too_complex')
        if isinstance(node, list):
            for index, value in enumerate(node): walk(value, location+'/'+str(index), server_index)
            return
        if not isinstance(node, dict): return
        entry = {'location': location}
        if 'match' in node:
            conditions = []
            for match in node['match'] if isinstance(node['match'], list) else []:
                if not isinstance(match, dict): continue
                host = match.get('host', [])
                if not isinstance(host, list): host = []
                paths = match.get('path', [])
                if not isinstance(paths, list): paths = []
                prefix_found |= any(isinstance(p, str) and (p == PREFIX or p.startswith(PREFIX+'/')) for p in paths)
                if HOST in host: expected_servers.add(server_index)
                headers = match.get('header', {})
                names = {str(k).lower() for k in headers} if isinstance(headers, dict) else set()
                conditions.append({'expected_host': HOST in host, 'host_condition_present':bool(host),
                    'path':[safe_path(p) for p in paths], 'header_condition_present':bool(names),
                    'x_api_key_condition':'x-api-key' in names,
                    'authorization_condition':'authorization' in names,
                    'other_conditions_present':bool(set(match)-{'host','path','header'}),
                    'negation_present':'not' in match})
            entry['match'] = conditions
        if 'terminal' in node: entry['terminal'] = bool(node['terminal'])
        if 'handler' in node:
            handler = node['handler']
            entry['handler'] = handler if handler in {'subroute','reverse_proxy','rewrite','static_response','headers','request_body','authentication'} else '<other-handler>'
            if handler == 'reverse_proxy':
                ports, other = upstreams(node.get('upstreams', []))
                entry['loopback_upstream_ports'] = ports; entry['other_upstream_present'] = other
            if handler == 'rewrite' and 'strip_path_prefix' in node:
                entry['strip_prefix'] = safe_path(node['strip_path_prefix'])
            if handler == 'static_response':
                status = str(node.get('status_code', ''))
                entry['response_status'] = int(status) if re.fullmatch('[1-5][0-9]{2}', status) else '<other-status>'
        if len(entry) > 1: output.append(entry)
        for key in ('routes', 'handle'):
            if key in node: walk(node[key], location+'/'+key, server_index)
    if not isinstance(servers, dict): raise ValueError('unexpected_http_servers')
    for index, server in enumerate(servers.values()):
        if isinstance(server, dict): walk(server.get('routes', []), 'server['+str(index)+']/routes', index)
    return {'servers_with_expected_host':len(expected_servers),
            'rooms_prefix_already_referenced':prefix_found,
            'routes':output[:MAX_NODES], 'truncated':len(output)>MAX_NODES,
            'logging_configuration_present': 'logging' in config,
            'access_logging_configured_on_any_http_server':any(isinstance(s,dict) and 'logs' in s for s in servers.values()),
            'log_redaction_verified':False}


def main():
    if os.geteuid() != 0:
        print(json.dumps({'result':'STOP','reason':'operator_root_console_required'})); return 1
    os.umask(0o077)
    try:
        states = {unit:service(unit) for unit in UNITS}
        opener = build_opener(NoRedirect())
        request = Request('http://127.0.0.1:2019/config/', headers={'Accept':'application/json'})
        with opener.open(request, timeout=15) as response:
            if response.status != 200: raise ValueError('unexpected_admin_response')
            raw = response.read(MAX_CONFIG_BYTES+1)
            if len(raw)>MAX_CONFIG_BYTES: raise ValueError('configuration_too_large')
            etag = response.headers.get('ETag')
        config = json.loads(raw)
        if not isinstance(config, dict): raise ValueError('invalid_configuration')
        summary = summarize(config)
        # A private evidence snapshot may include Caddy's existing auth secrets.
        # Never print it, send it to chat or restore the whole snapshot over newer config.
        directory = Path(tempfile.mkdtemp(prefix='mcp-rooms-proxy-inspect-', dir='/root'))
        snapshot = directory/'snapshot.json'
        with snapshot.open('x') as stream:
            json.dump({'format':1,'config':config,'etag':etag,'services':states}, stream)
        active = states['mcp-rooms-test.service']
        elapsed = None
        if active.get('ActiveState') == 'active':
            started = int(active.get('ActiveEnterTimestampMonotonic', '0'))
            if started>0: elapsed = max(0, int(time.monotonic()-started/1000000))
        print(json.dumps({'result':'SANITIZED ROOMS PROXY INSPECTION',
            'private_snapshot':str(snapshot), 'etag_available':bool(etag),
            'services':states, 'rooms_active_seconds':elapsed,
            **summary, 'configuration_changed':False, 'services_restarted':False,
            'public_route_created':False, 'registration_performed':False,
            'private_snapshot_created':True}, ensure_ascii=False))
        return 0
    except Exception:
        print(json.dumps({'result':'STOP','reason':'inspection_failed_no_details_disclosed',
                          'configuration_changed':False,'services_restarted':False})); return 1


if __name__ == '__main__':
    raise SystemExit(main())
