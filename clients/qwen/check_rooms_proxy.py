"""Read-only MCP handshake/list through a local proxy; no token required here."""
import argparse
import json
import sys
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from urllib.error import HTTPError
from urllib.parse import urlsplit

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8790/mcp')
    args = parser.parse_args()
    target = urlsplit(args.url)
    if not (target.scheme == 'http' and target.hostname == '127.0.0.1'
            and target.path == '/mcp' and not target.query and not target.fragment
            and not target.username and not target.password):
        print('STOP: only http://127.0.0.1:PORT/mcp is allowed.'); return 1
    opener = build_opener(ProxyHandler({}), NoRedirect())
    headers = {'Content-Type': 'application/json',
               'Accept': 'application/json, text/event-stream',
               'MCP-Protocol-Version': '2025-03-26'}
    def call(method, expected, request_id=None, params=None):
        payload = {'jsonrpc': '2.0', 'method': method}
        if request_id is not None: payload['id'] = request_id
        if params is not None: payload['params'] = params
        request = Request(args.url, data=json.dumps(payload).encode(),
                          headers=headers, method='POST')
        try:
            with opener.open(request, timeout=30) as response:
                status=response.status; raw=response.read(4*1024*1024+1)
                session=response.headers.get('Mcp-Session-Id')
        except HTTPError as exc:
            print(method + ': HTTP ' + str(exc.code))
            print('STOP: inspect sanitized proxy --debug lines.'); raise RuntimeError()
        print(method + ': HTTP ' + str(status))
        if status != expected or len(raw)>4*1024*1024: raise RuntimeError()
        if session: headers['Mcp-Session-Id']=session
        if request_id is None: return None
        result=json.loads(raw)
        if not isinstance(result,dict) or 'error' in result or result.get('id')!=request_id:
            raise RuntimeError()
        return result['result']
    try:
        result=call('initialize',200,1,{
            'protocolVersion':'2025-03-26','capabilities':{},
            'clientInfo':{'name':'local-rooms-proxy-check','version':'1.0'}})
        if result.get('protocolVersion')!='2025-03-26': raise RuntimeError()
        call('notifications/initialized',202)
        result=call('tools/list',200,2,{})
        actual={t['name'] for t in result['tools']}
        expected={'rooms_create','rooms_list','rooms_join','rooms_leave','rooms_read',
                  'rooms_send','rooms_delete_message','rooms_close'}
        if actual!=expected: raise RuntimeError()
        print('ROOM_TOOLS=8')
        print('PASS_LOCAL_PROXY_MCP')
        return 0
    except Exception as exc:
        print('STOP: ' + type(exc).__name__ + '; no room messages were sent.')
        return 1

if __name__=='__main__': sys.exit(main())
