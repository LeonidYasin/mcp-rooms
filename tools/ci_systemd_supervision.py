"""Synthetic cgroup-v2 proof ONLY in disposable GitHub-hosted Actions.

Not an installer, no application or credentials. Root required on ephemeral CI host.
Never use this diagnostic on VPS. Fixed fixture names; never overwrite existing ones.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

NAME='mcp-rooms-ci-supervision.service'
WORK=Path('/run/mcp-rooms-ci-supervision')
UNIT=Path('/run/systemd/system')/NAME
ENV={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'}


def run(*args,timeout=15):
    return subprocess.run(args,env=ENV,cwd='/',stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                          text=True,check=True,timeout=timeout).stdout


def props():
    result={}
    completed=subprocess.run(['/usr/bin/systemctl','show',NAME,'--no-pager',
        '--property=LoadState,ControlGroup,MainPID,ActiveState,FragmentPath,DropInPaths,KillMode'],
        env=ENV,cwd='/',stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,text=True,timeout=10)
    for line in completed.stdout.splitlines():
        k,v=line.split('=',1);result[k]=v
    if completed.returncode and not (completed.returncode==1 and result.get('LoadState')=='not-found'):
        raise RuntimeError('unit_observation_failed')
    return result


def live(pid):
    try:return Path('/proc/'+str(pid)+'/stat').read_text().rsplit(')',1)[1].split()[0]!='Z'
    except FileNotFoundError:return False


def main():
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.geteuid()!=0:
        raise RuntimeError('isolated_root_actions_only')
    if not Path('/sys/fs/cgroup/cgroup.controllers').is_file():
        raise RuntimeError('cgroup_v2_required')
    # A pre-existing fixture or unit is never adopted, stopped, removed or replaced.
    old=props()
    if UNIT.exists() or UNIT.is_symlink() or WORK.exists() or WORK.is_symlink() or old.get('FragmentPath') or old.get('MainPID')!='0':
        raise RuntimeError('existing_target_refused')
    work_created=False;unit_created=False;started=False
    try:
        WORK.mkdir(mode=0o755);work_created=True
        fixture=WORK/'fixture.py'
        fixture.write_text("import subprocess,sys,time\nparent=bytearray(8*1024*1024)\nchild=subprocess.Popen([sys.executable,'-I','-c',\"import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); data=bytearray(12*1024*1024); time.sleep(120)\"])\ntime.sleep(120)\n")
        fixture.chmod(0o644)
        with UNIT.open('x') as f:
            unit_created=True
            f.write('[Unit]\nDescription=Ephemeral MCP Rooms cgroup proof\n[Service]\nType=exec\nDynamicUser=yes\nExecStart=/usr/bin/python3 -I '+str(fixture)+'\nKillMode=control-group\nSendSIGKILL=yes\nTimeoutStopSec=2s\nRuntimeMaxSec=30s\nRestart=no\nNoNewPrivileges=yes\nCapabilityBoundingSet=\nProtectSystem=strict\nProtectHome=yes\nPrivateTmp=yes\nPrivateDevices=yes\nCPUAccounting=yes\nMemoryAccounting=yes\nTasksAccounting=yes\nMemoryMax=128M\nMemorySwapMax=0\nTasksMax=16\nCPUQuota=50%\nStandardOutput=null\nStandardError=null\n')
        UNIT.chmod(0o644)
        run('/usr/bin/systemd-analyze','verify',str(UNIT))
        run('/usr/bin/systemctl','daemon-reload')
        started=True;run('/usr/bin/systemctl','start',NAME)
        deadline=time.monotonic()+10
        while True:
            p=props();assert p['FragmentPath']==str(UNIT) and not p['DropInPaths'] and p['KillMode']=='control-group'
            cg=p['ControlGroup'];assert cg=='/system.slice/'+NAME
            group=Path('/sys/fs/cgroup'+cg);assert group.resolve()==group
            ids=[int(v) for v in (group/'cgroup.procs').read_text().split()]
            if len(ids)>=2 and int((group/'memory.current').read_text())>=32*1024*1024:break
            if time.monotonic()>deadline:raise RuntimeError('fixture_not_ready')
            time.sleep(.1)
        counters={k:(group/k).read_text().strip() for k in ('memory.current','memory.peak','memory.max','pids.current','pids.max','cpu.stat')}
        assert counters['memory.max']=='134217728' and counters['pids.max']=='16'
        assert int(counters['memory.peak'])>=int(counters['memory.current'])
        assert int(counters['pids.current'])>=2
        t=time.monotonic();run('/usr/bin/systemctl','stop',NAME);elapsed=time.monotonic()-t
        deadline=time.monotonic()+5
        while any(live(pid) for pid in ids) and time.monotonic()<deadline:time.sleep(.1)
        assert not any(live(pid) for pid in ids)
        assert not group.exists() or not (group/'cgroup.procs').read_text().strip()
        assert props()['MainPID']=='0'
        assert 1.5<=elapsed<10 # Child ignored TERM; cgroup stop forced cleanup after grace.
        print('SYSTEMD SUPERVISION PASS: '+json.dumps({'fixture_only':True,'application_tested':False,
            'cgroup_v2':True,'parent_and_term_resistant_child_stopped':True,
            'stop_seconds':round(elapsed,3),'aggregate_fixture_counters':counters,
            'vps_capacity_accepted':False},sort_keys=True))
    finally:
        # Only our newly-created fixture; do not touch any pre-existing unit.
        if unit_created:
            p=props()
            if p.get('FragmentPath')==str(UNIT) and not p.get('DropInPaths'):
                if started:run('/usr/bin/systemctl','stop',NAME)
                run('/usr/bin/systemctl','reset-failed',NAME)
            UNIT.unlink();run('/usr/bin/systemctl','daemon-reload')
        if work_created:shutil.rmtree(WORK)


if __name__=='__main__':main()
