"""Explicit same-origin session bridge for existing keys. No form or onboarding.

Cookie authority is deliberately NOT forwarded to market/media/MCP operations yet:
transaction-time session revocation binding must be accepted before that integration.
"""
from functools import partial
import json
import threading
import time
import anyio
from starlette.responses import JSONResponse
from .domain import DomainError

PATH = '/browser/session'
COOKIE = '__Host-mcp-rooms-session'
MAX_BODY = 1024
BODY_TIMEOUT_SECONDS = 10
HEADERS = {'Cache-Control':'no-store','Pragma':'no-cache','Vary':'Cookie, Origin',
    'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer',
    'Cross-Origin-Resource-Policy':'same-origin',
    'Content-Security-Policy':"default-src 'none'; frame-ancestors 'none'; base-uri 'none'"}


class Failure(Exception):
    def __init__(self, code, status):self.code,self.status=code,status


def values(scope,name):
    return [v.decode('latin1') for k,v in scope.get('headers',[]) if k.lower()==name]


class LoginBudget:
    """Bounded per-process fixed windows, not anti-bot or a fleet/IP limit."""
    def __init__(self,clock=time.monotonic):
        self.clock,self.lock=clock,threading.Lock()
        self.window=None;self.count=0;self.owners={}

    def take(self,credential=None):
        with self.lock:
            now=self.clock()
            if self.window is None or now<self.window or now>=self.window+60:
                self.window,self.count,self.owners=now,0,{}
            if credential is None:
                if self.count>=20:raise Failure('browser_login_throttled',429)
                self.count+=1
            else:
                if credential not in self.owners and len(self.owners)>=256:
                    raise Failure('browser_login_throttled',429)
                if self.owners.get(credential,0)>=3:
                    raise Failure('browser_login_throttled',429)
                self.owners[credential]=self.owners.get(credential,0)+1


def cookie(scope):
    entries=values(scope,b'cookie')
    if len(entries)>1 or sum(map(len,entries))>8192:
        raise Failure('invalid_cookie',400)
    found=[]
    for pair in entries[0].split(';') if entries else []:
        name,sep,value=pair.strip().partition('=')
        if name==COOKIE:
            if not sep:raise Failure('invalid_cookie',400)
            found.append(value)
    if len(found)>1:raise Failure('invalid_cookie',400)
    return found[0] if found else None


def _pairs(items):
    out={}
    for key,value in items:
        if key in out:raise ValueError('duplicate JSON member')
        out[key]=value
    return out


async def login_payload(scope,receive):
    if values(scope,b'content-type')!=['application/json']:
        raise Failure('json_required',415)
    lengths,transfer=values(scope,b'content-length'),values(scope,b'transfer-encoding')
    if (len(lengths)>1 or (transfer and (transfer!=['chunked'] or lengths))
            or values(scope,b'content-encoding')):
        raise Failure('invalid_body_framing',400)
    length=None
    if lengths:
        text=lengths[0]
        if not text.isascii() or not text.isdigit() or len(text)>10 or str(int(text))!=text:
            raise Failure('invalid_body_length',400)
        length=int(text)
        if length>MAX_BODY:raise Failure('body_too_large',413)
    body=bytearray()
    with anyio.fail_after(BODY_TIMEOUT_SECONDS):
        while True:
            event=await receive()
            if event['type']!='http.request':raise Failure('disconnected',400)
            chunk=event.get('body',b'')
            if len(chunk)>MAX_BODY-len(body):raise Failure('body_too_large',413)
            body.extend(chunk)
            if not event.get('more_body',False):break
    if length is not None and length!=len(body):raise Failure('invalid_body_length',400)
    try:payload=json.loads(bytes(body).decode('utf-8'),object_pairs_hook=_pairs)
    except (ValueError,UnicodeError):raise Failure('invalid_json',400) from None
    if (type(payload) is not dict or set(payload)-{'scopes'}
            or ('scopes' in payload and type(payload['scopes']) is not list)):
        raise Failure('invalid_login_arguments',400)
    return payload.get('scopes',['listings:read'])


class BrowserHTTP:
    def __init__(self,sessions,auth,origin,authority):
        self.sessions,self.auth=sessions,auth
        self.origin,self.authority=origin,authority
        self.budget,self.slots=LoginBudget(),threading.BoundedSemaphore(8)

    def policy(self,scope):
        if scope.get('scheme')!='https' or values(scope,b'host')!=[self.authority]:
            raise Failure('browser_https_required',400)
        origins,sites=values(scope,b'origin'),values(scope,b'sec-fetch-site')
        modes,dest=values(scope,b'sec-fetch-mode'),values(scope,b'sec-fetch-dest')
        if sites and sites!=['same-origin']:raise Failure('invalid_origin',403)
        if modes and modes not in (['same-origin'],['cors']):raise Failure('invalid_origin',403)
        metadata_get=(scope['method']=='GET' and not origins and sites==['same-origin']
                      and modes==['same-origin'] and dest==['empty'])
        if origins!=[self.origin] and not metadata_get:raise Failure('invalid_origin',403)
        if scope['method'] not in {'GET','POST','DELETE'}:raise Failure('method_not_allowed',405)

    @staticmethod
    def reply(payload,status=200):
        return JSONResponse(payload,status_code=status,headers=HEADERS)

    @staticmethod
    def clear(response):
        response.delete_cookie(COOKIE,path='/',secure=True,httponly=True,samesite='strict')
        return response

    @staticmethod
    def context(context):
        return {'ok':True,'user_id':context.principal.user_id,'owner':context.principal.owner,
            'scopes':sorted(context.principal.scopes),'expires_at':context.expires_at,
            'csrf_token':context.csrf_token}

    async def operation(self,scope,receive):
        self.policy(scope)
        method=scope['method'];raw=cookie(scope)
        if method=='POST':
            # No silent switch/fixation/rotation: logout first. Bootstrap clears an
            # invalid/expired cookie under the same-origin policy.
            if raw is not None:raise Failure('browser_logout_required',409)
            self.budget.take()
            auth=values(scope,b'authorization')
            actor=None
            if len(auth)==1 and len(auth[0])<=512:
                scheme,sep,key=auth[0].partition(' ')
                if sep and scheme.lower()=='bearer':
                    actor=await anyio.to_thread.run_sync(self.auth.authenticate,key)
            if actor is None:raise Failure('invalid_token',401)
            self.budget.take(actor.credential_id)
            selected=await login_payload(scope,receive)
            issued=await anyio.to_thread.run_sync(partial(self.sessions.create,actor,scopes=selected))
            response=self.reply(self.context(issued.context),201)
            age=max(0,(issued.context.expires_at-self.sessions.store.clock())//1000)
            response.set_cookie(COOKIE,issued.cookie,max_age=age,path='/',
                                secure=True,httponly=True,samesite='strict')
            return response
        if values(scope,b'authorization'):raise Failure('mixed_browser_credentials',400)
        if (values(scope,b'transfer-encoding') or values(scope,b'content-encoding')
                or values(scope,b'content-length') not in ([],['0'])):
            raise Failure('body_not_supported',400)
        if method=='GET':
            context=await anyio.to_thread.run_sync(self.sessions.resolve,raw)
            return self.reply(self.context(context))
        csrf=values(scope,b'x-csrf-token')
        if len(csrf)!=1:raise Failure('browser_csrf_required',403)
        result=await anyio.to_thread.run_sync(partial(self.sessions.logout,raw,csrf_token=csrf[0]))
        return self.clear(self.reply(result))

    async def response(self,scope,receive):
        try:return await self.operation(scope,receive)
        except Failure as exc:code,status=exc.code,exc.status
        except DomainError as exc:
            code=exc.code
            if code in {'browser_session_required','authentication_required'}:status=401
            elif code=='insufficient_scope':status=403 if scope['method']=='POST' else 401
            elif code=='browser_csrf_required':status=403
            elif code in {'invalid_browser_scopes','invalid_browser_lifetime'}:status=400
            elif code in {'browser_session_capacity','browser_owner_session_capacity'}:status=429
            else:code,status='browser_unavailable',503
        except TimeoutError:code,status='request_timeout',408
        except Exception:code,status='browser_unavailable',503
        response=self.reply({'ok':False,'error':code},status)
        if code=='browser_login_throttled':response.headers['Retry-After']='60'
        if code=='method_not_allowed':response.headers['Allow']='GET, POST, DELETE'
        if status==401 and scope['method']=='GET':self.clear(response)
        return response

    async def handle(self,scope,receive,send):
        # No queue. Hold admission through response sending; do not catch send errors
        # as application errors or try a second response after response-start.
        if not self.slots.acquire(blocking=False):
            response=self.reply({'ok':False,'error':'browser_http_busy'},429)
            response.headers['Retry-After']='1'
            return await response(scope,receive,send)
        try:
            response=await self.response(scope,receive)
            return await response(scope,receive,send)
        finally:self.slots.release()
