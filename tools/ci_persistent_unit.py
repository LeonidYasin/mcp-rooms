"""Real persistent-unit policy proof ONLY on disposable GitHub-hosted Actions.

Proves, under a real systemd, the semantics the operator tools rely on:
`Restart=on-failure` restarts a killed process, there is no runtime ceiling,
`systemctl enable/disable` create/remove the boot symlink, and enable does not start.

This is a synthetic fixture plus a syntax/content check of the real rendered unit.
It is not the application, not an installer, not a VPS and not production acceptance.
Never run this on the owner's VPS.
"""
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
NAME='mcp-rooms-ci-persistent.service'
WORK=Path('/run/mcp-rooms-ci-persistent')
UNIT=Path('/run/systemd/system')/NAME
WANTS=Path('/etc/systemd/system/multi-user.target.wants')/NAME
ENV={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'}


def run(*args,timeout=30):
    return subprocess.run(args,env=ENV,cwd='/',stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,check=True,timeout=timeout).stdout


def props():
    completed=subprocess.run(['/usr/bin/systemctl','show',NAME,'--no-pager',
        '--property=LoadState,ActiveState,SubState,MainPID,FragmentPath,DropInPaths,'\
        'KillMode,RuntimeMaxUSec,UnitFileState,NRestarts'],
        env=ENV,cwd='/',stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,text=True,timeout=10)
    values={}
    for line in completed.stdout.splitlines():
        key,value=line.split('=',1);values[key]=value
    if completed.returncode and values.get('LoadState')!='not-found':
        raise RuntimeError('unit_observation_failed')
    return values


def enabled():
    completed=subprocess.run(['/usr/bin/systemctl','is-enabled',NAME],env=ENV,cwd='/',
        stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
        text=True,timeout=10)
    return completed.stdout.strip()


def rendered(source):
    return runpy.run_path(str(ROOT/'tools/operator_unit.py'))['render'](
        source,'https://candidate.invalid/rooms-candidate/mcp',True)


def check_rendering(source):
    persistent=rendered(source)
    transient=runpy.run_path(str(ROOT/'tools/operator_unit.py'))['render'](
        source,'https://candidate.invalid/rooms-candidate/mcp')
    assert 'Restart=on-failure' in persistent,'persistent_restart_policy'
    assert 'RestartSec=5s' in persistent,'persistent_restart_delay'
    assert 'RuntimeMaxSec=' not in persistent,'persistent_runtime_ceiling'
    assert '[Install]' in persistent and 'WantedBy=multi-user.target' in persistent,'persistent_boot_target'
    assert 'RuntimeMaxSec=2h' in transient and '[Install]' not in transient,'transient_shape_changed'
    for directive in ('NoNewPrivileges=yes','ProtectSystem=strict','MemoryMax=1G','TasksMax=64'):
        assert directive in persistent,'persistent_hardening_lost'
    # Syntax-check the real rendered unit with a synthetic executable only.
    syntax=persistent.replace([line for line in persistent.splitlines() if line.startswith('ExecStart=')][0],
        'ExecStart=/usr/bin/sleep 120')
    path=Path('/tmp/mcp-rooms-ci-persistent-syntax.service')
    path.write_text(syntax)
    run('/usr/bin/systemd-analyze','verify',str(path))
    path.unlink()
    return {'persistent_restart':'on-failure','runtime_ceiling':None,
            'boot_target':'multi-user.target','transient_shape_unchanged':True}


def fixture_unit():
    script=WORK/'fixture.py'
    script.write_text('import time\ntime.sleep(120)\n')
    script.chmod(0o644)
    return ('[Unit]\nDescription=Ephemeral MCP Rooms persistent-unit proof\n'
        '[Service]\nType=exec\n'
        'ExecStart=/usr/bin/python3 -I '+str(script)+'\n'
        'Restart=on-failure\nRestartSec=1s\n'
        'KillMode=control-group\nSendSIGKILL=yes\n'
        'TimeoutStartSec=30s\nTimeoutStopSec=10s\n'
        'NoNewPrivileges=yes\nCapabilityBoundingSet=\n'
        'ProtectSystem=strict\nProtectHome=yes\nPrivateTmp=yes\n'
        'StandardOutput=null\nStandardError=null\n'
        '[Install]\nWantedBy=multi-user.target\n')


def await_active(previous=None,deadline=20):
    limit=time.monotonic()+deadline
    while time.monotonic()<limit:
        p=props()
        if p.get('ActiveState')=='active' and p.get('MainPID') not in ('0','') and p.get('MainPID')!=previous:
            return p
        time.sleep(.1)
    raise RuntimeError('unit_not_active')


def main(argv=None):
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.geteuid()!=0:
        raise RuntimeError('isolated_root_actions_only')
    if not Path('/sys/fs/cgroup/cgroup.controllers').is_file():
        raise RuntimeError('cgroup_v2_required')
    source=(argv or sys.argv[1:] or [''])[0]
    check_rendering(source)
    old=props()
    if UNIT.exists() or UNIT.is_symlink() or WORK.exists() or WORK.is_symlink() or WANTS.exists() or WANTS.is_symlink() \
            or old.get('FragmentPath') or old.get('MainPID')!='0':
        raise RuntimeError('existing_target_refused')
    unit_created=started=False
    try:
        WORK.mkdir(mode=0o755)
        with UNIT.open('x') as stream:
            unit_created=True;stream.write(fixture_unit())
        UNIT.chmod(0o644)
        run('/usr/bin/systemd-analyze','verify',str(UNIT))
        run('/usr/bin/systemctl','daemon-reload')
        run('/usr/bin/systemctl','start',NAME);started=True
        first=await_active()
        p=props()
        assert p['FragmentPath']==str(UNIT) and not p['DropInPaths'],'fixture_unit_identity'
        assert p['RuntimeMaxUSec']=='infinity','unexpected_runtime_ceiling'
        print('PERSISTENT STEP: no-runtime-ceiling',flush=True)
        run('/usr/bin/systemctl','enable',NAME)
        assert enabled()=='enabled','enable_not_confirmed'
        assert WANTS.is_symlink(),'boot_symlink_missing'
        mid=props()
        assert mid['ActiveState']=='active' and mid['MainPID']==first['MainPID'],'enable_started_or_restarted'
        print('PERSISTENT STEP: enable-without-start',flush=True)
        os.kill(int(first['MainPID']),9)
        second=await_active(previous=first['MainPID'])
        restarts=int(props()['NRestarts'])
        assert restarts>=1,'restart_policy_not_observed'
        print('PERSISTENT STEP: restart-on-failure',flush=True)
        run('/usr/bin/systemctl','disable',NAME)
        assert enabled()=='disabled','disable_not_confirmed'
        assert not WANTS.exists() and not WANTS.is_symlink(),'boot_symlink_left'
        after=props()
        assert after['ActiveState']=='active' and after['MainPID']==second['MainPID'],'disable_stopped_the_unit'
        print('PERSISTENT STEP: disable-without-stop',flush=True)
        run('/usr/bin/systemctl','stop',NAME)
        deadline=time.monotonic()+10
        while props().get('ActiveState')!='inactive' and time.monotonic()<deadline:time.sleep(.1)
        assert props()['ActiveState']=='inactive','stop_not_confirmed'
        started=False
        print('PERSISTENT UNIT PASS: '+json.dumps({'source_sha':source,'restart_policy':'on-failure',
            'runtime_ceiling':None,'boot_target':'multi-user.target','enable_does_not_start':True,
            'disable_does_not_stop':True,'nrestarts':restarts,'vps':False,
            'application_source_unchanged':True},sort_keys=True),flush=True)
    finally:
        try:
            if started:run('/usr/bin/systemctl','stop',NAME,timeout=25)
        except Exception:pass
        try:
            if enabled()=='enabled':run('/usr/bin/systemctl','disable',NAME)
        except Exception:pass
        if unit_created and (UNIT.exists() or UNIT.is_symlink()):UNIT.unlink()
        if WANTS.exists() or WANTS.is_symlink():WANTS.unlink()
        run('/usr/bin/systemctl','daemon-reload')
        if WORK.exists():shutil.rmtree(WORK,ignore_errors=True)
        try:run('/usr/bin/systemctl','reset-failed',NAME)
        except Exception:pass


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('PERSISTENT UNIT FAILED: '+json.dumps({'exception':type(exc).__name__,
            'message':str(exc)[:200]}),flush=True)
        raise SystemExit(1)
