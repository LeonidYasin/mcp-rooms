"""Real installed candidate under exact reviewed unit on disposable Actions ONLY.

NOT a VPS installer. This privileged CI harness creates fixed ephemeral identities,
root-owned code and synthetic private state, and removes them during CI teardown.
No live keys, artifacts, Caddy, external route, boot enable or application imports.
"""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import grp
import http.client
import json
import os
from pathlib import Path
import pwd
import re
import runpy
import shutil
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import uuid
import zlib

ROOT=Path(__file__).resolve().parents[1]
USER='mcp-rooms-candidate'
NAME=USER+'.service'
BASE=Path('/opt')/USER
STATE=Path('/var/lib')/USER
PROFILE=STATE/'owner-first'
UNIT=Path('/run/systemd/system')/NAME
RESOURCE='https://candidate.invalid/rooms-candidate/mcp'
ENV={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','PYTHONUTF8':'1'}
LIMIT=1024*1024


def command(args,timeout=120):
    # Output may contain pip/bootstrap details; never print it or raw subprocess errors.
    try:
        return subprocess.run(args,env=ENV,cwd='/',stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,timeout=timeout).stdout
    except subprocess.CalledProcessError as exc:
        stderr=exc.stderr or b'';stdout=exc.stdout or b''
        categories={name:needle in stderr or needle in stdout for name,needle in (
            ('permission',b'Permission denied'),('missing_file',b'No such file'),
            ('libpython',b'libpython'),('ensurepip',b'ensurepip'),
            ('readonly',b'Read-only file system'),('candidate_storage',b'candidate_storage_error'),
            ('candidate_unavailable',b'candidate_unavailable'))}
        print('CI COMMAND FAILURE: '+json.dumps({'caller_line':sys._getframe(1).f_lineno,
            'program':Path(args[0]).name,'returncode':exc.returncode,'categories':categories}),flush=True)
        raise


def properties():
    result={}
    args=['/usr/bin/systemctl','show',NAME,'--no-pager',
        '--property=LoadState,ControlGroup,MainPID,ActiveState,FragmentPath,DropInPaths,User,Group,KillMode,MemoryMax,TasksMax']
    c=subprocess.run(args,env=ENV,cwd='/',stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,timeout=15)
    for line in c.stdout.splitlines():
        k,v=line.split('=',1);result[k]=v
    if c.returncode and not (c.returncode==1 and result.get('LoadState')=='not-found'):
        raise RuntimeError('candidate_unit_observation_failed')
    return result


def request(method,path,raw=None,body=None,headers=None,timeout=20):
    # TCP stays loopback; public reads require the configured canonical Host.
    h={'Host':'candidate.invalid',**(headers or {})}
    if raw is not None:h['Authorization']='Bearer '+raw
    c=http.client.HTTPConnection('127.0.0.1',8766,timeout=timeout)
    try:
        c.request(method,path,body=body,headers=h)
        response=c.getresponse();data=response.read(LIMIT+1)
        assert len(data)<=LIMIT
        return response.status,data
    finally:c.close()


def rpc(raw,method,params):
    status,body=request('POST','/mcp',raw,json.dumps({'jsonrpc':'2.0','id':1,
        'method':method,'params':params}),{'Content-Type':'application/json',
        'Accept':'application/json, text/event-stream','MCP-Protocol-Version':'2025-11-25'})
    assert status==200,'candidate_rpc_status'
    result=json.loads(body)['result']
    if method=='tools/call':
        result=json.loads(result['content'][0]['text']);assert result['ok'],'candidate_tool_failure'
    return result


def call(raw,name,**arguments):return rpc(raw,'tools/call',{'name':name,'arguments':arguments})
def key():return str(uuid.uuid4())


def synthetic_png(width=4000,height=3000):
    def chunk(kind,data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    c=zlib.compressobj();parts=[];row=b'\0'+b'\x20\x90\x40'*width
    for _ in range(height):parts.append(c.compress(row))
    parts.append(c.flush())
    return (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+
        chunk(b'tEXt',b'Comment\0CI-SYNTHETIC-METADATA')+chunk(b'IDAT',b''.join(parts))+chunk(b'IEND',b''))


def jpeg_dimensions(data):
    if not data.startswith(b'\xff\xd8') or not data.endswith(b'\xff\xd9'):raise ValueError('invalid_jpeg')
    offset=2
    while offset+4<=len(data):
        if data[offset]!=255:raise ValueError('invalid_jpeg')
        marker=data[offset+1];offset+=2
        if marker==218:break
        length=int.from_bytes(data[offset:offset+2],'big')
        if length<2 or offset+length>len(data):raise ValueError('invalid_jpeg')
        if marker in (192,193,194):
            if length<8:raise ValueError('invalid_jpeg')
            return int.from_bytes(data[offset+5:offset+7],'big'),int.from_bytes(data[offset+3:offset+5],'big')
        offset+=length
    raise ValueError('jpeg_dimensions_missing')


def upload_headers():
    return {'Content-Type':'image/png','X-Expected-Revision':'1','Idempotency-Key':key()}


def partial_upload(raw,path):
    c=http.client.HTTPConnection('127.0.0.1',8766,timeout=15)
    c.putrequest('POST',path)
    for k,v in {'Authorization':'Bearer '+raw,'Content-Length':'100',**upload_headers()}.items():c.putheader(k,v)
    c.endheaders();c.send(b'\x89');return c


def children(group):
    result=[]
    for entry in (group/'cgroup.procs').read_text().split():
        pid=int(entry)
        try:argv=Path('/proc/'+entry+'/cmdline').read_bytes().split(b'\0')
        except FileNotFoundError:continue
        if b'mcp_rooms.media_worker_child' in argv and b'--sandbox' in argv:result.append(pid)
    return result


def cpu(group):
    return {k:int(v) for k,v in (line.split() for line in (group/'cpu.stat').read_text().splitlines())}


class Sampler:
    def __init__(self,group):
        self.group=group;self.done=threading.Event();self.error=None
        self.memory=0;self.tasks=0;self.native=0;self.seen=set()
        self.thread=threading.Thread(target=self._sample,daemon=True)
    def _sample(self):
        try:
            while not self.done.is_set():
                self.memory=max(self.memory,int((self.group/'memory.current').read_text()))
                self.tasks=max(self.tasks,int((self.group/'pids.current').read_text()))
                ids=children(self.group);self.native=max(self.native,len(ids));self.seen.update(ids)
                self.done.wait(.005)
        except BaseException as exc:self.error=type(exc).__name__
    def start(self):self.thread.start()
    def stop(self):
        self.done.set();self.thread.join(timeout=5)
        assert not self.thread.is_alive() and self.error is None,'candidate_sampler_failed'


def running(uid):
    p=properties()
    assert p['FragmentPath']==str(UNIT) and not p['DropInPaths'],'candidate_unit_identity'
    assert p['User']==p['Group']==USER and p['KillMode']=='control-group'
    assert p['MemoryMax']==str(1024**3) and p['TasksMax']=='64'
    assert p['ControlGroup']=='/system.slice/'+NAME
    pid=int(p['MainPID']);assert pid>0
    proc=Path('/proc')/str(pid)
    assert proc.stat().st_uid==uid
    argv=(proc/'cmdline').read_bytes().split(b'\0')
    assert b'mcp_rooms.test_candidate' in argv and str(PROFILE).encode() in argv
    caps=(proc/'status').read_text()
    assert all(int(next(v.split()[1] for v in caps.splitlines() if v.startswith(k+':')),16)==0
               for k in ('CapEff','CapPrm','CapInh','CapAmb'))
    group=Path('/sys/fs/cgroup'+p['ControlGroup']);assert group.resolve()==group
    return group


def await_ready(uid):
    deadline=time.monotonic()+25
    while True:
        p=properties()
        if p.get('ActiveState')=='failed':raise RuntimeError('candidate_unit_start_failed')
        try:
            status,_=request('POST','/mcp',body=b'{}',headers={'Content-Type':'application/json'},timeout=1)
            if status==401:return running(uid)
        except OSError:pass
        if time.monotonic()>deadline:raise RuntimeError('candidate_unit_not_ready')
        time.sleep(.1)


def stop_owned():
    p=properties()
    assert p.get('FragmentPath')==str(UNIT) and not p.get('DropInPaths'),'candidate_stop_identity_refused'
    command(['/usr/bin/systemctl','stop',NAME],timeout=25)
    assert properties()['MainPID']=='0'
    group=Path('/sys/fs/cgroup/system.slice')/NAME
    assert not group.exists() or not (group/'cgroup.procs').read_text().strip()


def immutable(root):
    for p in [root,*root.rglob('*')]:
        if p.is_symlink():
            assert p.resolve().is_relative_to(root),'candidate_external_code_link'
            os.lchown(p,0,0);continue
        info=p.stat();os.chown(p,0,0)
        p.chmod(0o755 if p.is_dir() or info.st_mode&0o111 else 0o644)
    assert all(p.lstat().st_uid==0 for p in [root,*root.rglob('*')])


def account_absent():
    for getter in (pwd.getpwnam,grp.getgrnam):
        try:getter(USER)
        except KeyError:continue
        raise RuntimeError('candidate_existing_identity')


def main(bundle,source,python_base):
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.geteuid()!=0 or sys.version_info[:2]!=(3,12):
        raise RuntimeError('disposable_actions_root_only')
    if not re.fullmatch('[0-9a-f]{40}',source):raise RuntimeError('candidate_invalid_source')
    if not Path('/sys/fs/cgroup/cgroup.controllers').is_file():raise RuntimeError('cgroup_v2_required')
    python_base=Path(python_base)
    if not python_base.is_absolute() or python_base.resolve()!=python_base or not str(python_base).startswith('/opt/hostedtoolcache/Python/3.12.'):
        raise RuntimeError('candidate_ci_interpreter_required')
    assert (python_base/'bin/python3.12').is_file()
    old=properties()
    account_absent()
    targets=[BASE,STATE,UNIT,Path('/etc/systemd/system')/NAME,
        Path('/etc/systemd/system')/(NAME+'.d'),Path(str(UNIT)+'.d')]
    if any(p.exists() or p.is_symlink() for p in targets) or old.get('FragmentPath') or old.get('MainPID')!='0':
        raise RuntimeError('candidate_existing_target')
    with socket.socket() as probe:probe.bind(('127.0.0.1',8766))
    created_user=False;created_base=False;created_state=False;created_unit=False;loaded=False
    sampler=None;raw=None
    try:
        command(['/usr/sbin/useradd','--system','--user-group','--no-create-home','--home-dir',str(STATE),'--shell','/usr/sbin/nologin',USER])
        created_user=True;uid=pwd.getpwnam(USER).pw_uid;gid=grp.getgrnam(USER).gr_gid
        BASE.mkdir(mode=0o755);created_base=True
        release=BASE/'releases'/source;release.mkdir(parents=True,mode=0o755)
        interpreter=release/'python';shutil.copytree(python_base,interpreter,symlinks=False)
        immutable(interpreter)
        STATE.mkdir(mode=0o700);created_state=True;os.chown(STATE,uid,gid)
        venv=release/'venv';venv.mkdir(mode=0o755);os.chown(venv,uid,gid)
        run_as=['/usr/sbin/runuser','-u',USER,'--']
        command([*run_as,str(interpreter/'bin/python3.12'),'-I','-m','venv','--copies',str(venv)])
        # Verify root-private copy before exposing read-only wheel bytes to install user.
        with tempfile.TemporaryDirectory(prefix='rooms-root-bundle-') as temp:
            verified=Path(temp)/'bundle';shutil.copytree(bundle,verified)
            lock=sha256((ROOT/'operator/runtime-linux-x86_64-py312.lock').read_bytes()).hexdigest()
            runpy.run_path(str(ROOT/'tools/operator_bundle.py'))['verify'](verified,source,lock)
            wheels=BASE/'bootstrap-wheelhouse';shutil.copytree(verified,wheels)
            immutable(wheels)
            command([*run_as,str(venv/'bin/python'),'-I','-m','pip','--isolated','install',
                '--disable-pip-version-check','--no-index','--no-deps','--only-binary=:all:',
                '--find-links',str(wheels/'wheels'),'--require-hashes','-r',str(wheels/'install.lock')])
            command([*run_as,str(venv/'bin/python'),'-I','-m','pip','check'])
        immutable(venv)
        cli=[*run_as,str(venv/'bin/python'),'-I','-m','mcp_rooms.test_candidate']
        command([*cli,'bootstrap','--state',str(PROFILE),'--resource',RESOURCE])
        raw=(PROFILE/'owner.key').read_text().strip()
        key_hash=sha256((PROFILE/'owner.key').read_bytes()).hexdigest()
        rendered=runpy.run_path(str(ROOT/'tools/operator_unit.py'))['render'](source,RESOURCE)
        with UNIT.open('x') as f:created_unit=True;f.write(rendered)
        UNIT.chmod(0o644)
        command(['/usr/bin/systemd-analyze','verify',str(UNIT)])
        command(['/usr/bin/systemctl','daemon-reload']);loaded=True
        command(['/usr/bin/systemctl','start',NAME])
        group=await_ready(uid);start_cpu=cpu(group)['usage_usec']
        print('CANDIDATE UNIT STEP: unit-ready',flush=True)
        sampler=Sampler(group);sampler.start()
        assert rpc(raw,'initialize',{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'systemd-ci','version':'1'}})['serverInfo']['name']=='MCP Rooms'
        assert len(rpc(raw,'tools/list',{})['tools'])==20
        listing=call(raw,'listings_create',client_id=key(),category_id='things',content={
            'title':'CI synthetic unit item','description':'Synthetic; not a real offer',
            'category':'things','kind':'offer','modes':['shipping']})['listing']['id']
        path='/listings/'+listing+'/photos'
        image=synthetic_png()
        # Real slow-body admission and10s timeout, no application monkeypatches.
        slow=partial_upload(raw,path)
        try:
            time.sleep(.4)
            status,_=request('POST',path,raw,image,upload_headers());assert status==429,'candidate_admission_not_enforced'
            response=slow.getresponse();assert response.status==408
            assert json.loads(response.read(LIMIT))['error']=='request_timeout'
        finally:slow.close()
        disconnect=partial_upload(raw,path);time.sleep(.3);disconnect.close()
        deadline=time.monotonic()+3
        while True:
            status,data=request('POST',path,raw,image,upload_headers())
            if status!=429:break
            assert time.monotonic()<deadline,'candidate_disconnect_slot_leaked';time.sleep(.1)
        assert status==201,'candidate_photo_upload_failed'
        media=json.loads(data)['media_id']
        print('CANDIDATE UNIT STEP: native-photo',flush=True)
        # Exact candidate child receives STOP through a pinned handle; real8s
        # worker wall timer must then kill/reap it and return a typed504.
        with ThreadPoolExecutor(max_workers=1) as pool:
            t=time.monotonic();future=pool.submit(request,'POST',path,raw,image,upload_headers())
            injected=False;deadline=time.monotonic()+4
            while not future.done() and time.monotonic()<deadline:
                for pid in children(group):
                    try:fd=os.pidfd_open(pid)
                    except ProcessLookupError:continue
                    try:
                        argv=(Path('/proc')/str(pid)/'cmdline').read_bytes().split(b'\0')
                        expected=[str(venv/'bin/python').encode(),b'-I',b'-B',b'-m',b'mcp_rooms.media_worker_child',b'--sandbox',str(PROFILE).encode(),b'']
                        assert argv==expected and (Path('/proc')/str(pid)).stat().st_uid==uid
                        assert pid in children(group)
                        signal.pidfd_send_signal(fd,signal.SIGSTOP);injected=True
                    except FileNotFoundError:continue
                    finally:os.close(fd)
                    break
                if injected:break
                time.sleep(.001)
            assert injected,'candidate_native_fault_not_injected'
            status,data=future.result(timeout=16);elapsed=time.monotonic()-t
            assert status==504 and json.loads(data)['error']=='media_worker_timeout','candidate_native_timeout_failed'
            assert 7<=elapsed<16
        assert not children(group),'candidate_native_child_leaked'
        print('CANDIDATE UNIT STEP: native-timeout-reaped',flush=True)
        status,_=request('POST',path,raw,image,upload_headers());assert status==201,'candidate_native_slot_leaked'
        call(raw,'listings_set_photos',listing_id=listing,expected_revision=1,client_id=key(),media_ids=[media])
        preview=call(raw,'listings_preview',listing_id=listing)
        consent=call(raw,'listings_confirm_publication',listing_id=listing,expected_revision=2,
            preview_digest=preview['digest'],consent=True,client_id=key())
        published=call(raw,'listings_publish',listing_id=listing,intent_id=consent['intent_id'],client_id=key())
        card='/market/'+listing;photo=card+'/photos/'+str(published['publication_revision'])+'/'+media+'.jpg'
        assert request('GET',card,headers={'Host':'127.0.0.1:8766'})[0]==421,'candidate_public_host_gate'
        status,data=request('GET',card);assert status==200 and b'CI synthetic unit item' in data
        status,data=request('GET',photo);assert status==200 and jpeg_dimensions(data)==(1600,1200)
        assert b'CI-SYNTHETIC-METADATA' not in data and b'Exif\0\0' not in data
        call(raw,'listings_withdraw',listing_id=listing,expected_publication_revision=1,client_id=key())
        assert request('GET',card)[0]==request('GET',photo)[0]==404
        sampler.stop();assert sampler.native==1 and sampler.seen,'candidate_native_sampling_missing'
        print('CANDIDATE UNIT STEP: publication-withdraw',flush=True)
        events={k:int(v) for k,v in (line.split() for line in (group/'memory.events').read_text().splitlines())}
        peak=int((group/'memory.peak').read_text());cpu_used=cpu(group)['usage_usec']-start_cpu
        assert events['oom_kill']==0 and peak<1024**3 and sampler.tasks<=64 and cpu_used>0
        state_files=[p for p in STATE.rglob('*') if p.is_file()]
        logical=sum(p.stat().st_size for p in state_files);allocated=sum(p.stat().st_blocks*512 for p in state_files)
        assert logical<64*1024**2 and allocated<64*1024**2
        stop_owned();assert (PROFILE/'market.sqlite3').exists()
        command(['/usr/bin/systemctl','start',NAME]);group=await_ready(uid)
        assert call(raw,'listings_get',listing_id=listing)['ok']
        assert request('GET',card)[0]==request('GET',photo)[0]==404
        assert sha256((PROFILE/'owner.key').read_bytes()).hexdigest()==key_hash
        stop_owned();assert (PROFILE/'market.sqlite3').exists()
        print('CANDIDATE UNIT STEP: restart-preserved',flush=True)
        print('CANDIDATE UNIT PASS: '+json.dumps({'source_sha':source,'exact_rendered_unit':True,
            'root_owned_release':True,'offline_nonroot_pip':True,'nonroot_service':True,
            'real_native_photo':True,'http_admission_429':True,'body_timeout_408':True,
            'disconnect_slot_released':True,'native_fault_timeout_504_and_reaped':True,
            'native_timeout_seconds':round(elapsed,3),'native_slot_reused':True,
            'public_card_photo_withdraw':True,'wrong_public_host_421':True,'restart_key_listing_withdrawal_preserved':True,
            'cgroup_memory_peak_bytes':peak,'sampled_tasks_peak':sampler.tasks,
            'sampled_native_parallel_peak':sampler.native,'cgroup_cpu_usage_usec':cpu_used,
            'state_logical_bytes':logical,'state_allocated_bytes':allocated,
            'fixture_capacity_bounds_only':True,'vps_capacity_accepted':False,
            'production_installer':False},sort_keys=True))
    finally:
        raw=None
        if sampler is not None and sampler.thread.is_alive():sampler.stop()
        safe=True
        if created_unit:
            p=properties()
            if loaded and p.get('FragmentPath')==str(UNIT) and not p.get('DropInPaths'):
                stop_owned()
                # Inactive successful units can already be garbage-collected;
                # reset-failed does not load them and must not mask test errors.
                if properties().get('ActiveState')=='failed':
                    command(['/usr/bin/systemctl','reset-failed',NAME])
            elif loaded:safe=False
            if safe:UNIT.unlink();command(['/usr/bin/systemctl','daemon-reload'])
        # Teardown of disposable synthetic fixture is NOT operator rollback.
        if safe:
            if created_state:shutil.rmtree(STATE)
            if created_base:shutil.rmtree(BASE)
            if created_user:command(['/usr/sbin/userdel',USER])
        else:raise RuntimeError('candidate_ci_teardown_identity_refused')


if __name__=='__main__':
    try:main(Path(sys.argv[1]),sys.argv[2],sys.argv[3])
    except Exception as exc:
        # Do not stringify subprocess exception/argv/stdout or HTTP payloads.
        frames=[f for f in traceback.extract_tb(exc.__traceback__) if f.filename==__file__]
        frame=next((f for f in reversed(frames) if f.name=='main'),frames[-1] if frames else traceback.extract_tb(exc.__traceback__)[-1])
        print('CANDIDATE UNIT FAILED: '+json.dumps({'exception':type(exc).__name__,
            'function':frame.name,'line':frame.lineno}),file=sys.stderr)
        raise SystemExit(1)
