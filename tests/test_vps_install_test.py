"""Installer pure/mocked tests. No real systemctl, useradd, network or VPS calls."""
import ast
import hashlib
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
import pytest
from starlette.testclient import TestClient
from mcp_rooms.server import create_app

spec = importlib.util.spec_from_file_location('vps_install_test', Path(__file__).parents[1] / 'deploy/vps_install_test.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


def test_nonroot_never_opens_lock_or_runs_commands(monkeypatch, capsys):
    monkeypatch.setattr(m.os, 'geteuid', lambda: 1000)
    def forbidden(*args, **kwargs): raise AssertionError('operator-only action')
    monkeypatch.setattr(m.os, 'open', forbidden)
    monkeypatch.setattr(m, 'capture', forbidden)
    assert m.main(['--install']) == 1
    assert 'operator_root_console_required' in capsys.readouterr().out


def test_port_parser_and_fixed_runtime_pin():
    assert m.port_free('LISTEN 0 10 127.0.0.1:3001 0.0.0.0:*')
    for host in ('127.0.0.1', '0.0.0.0', '[::]', '*'):
        assert not m.port_free(f'LISTEN 0 10 {host}:8765 *:*')
    assert m.SOURCE == '4b2351c0b6522d30c888496b3c1774be8791345f'
    assert m.UNIT_HASH == hashlib.sha256(m.UNIT_TEXT.encode()).hexdigest()
    assert 'User=mcp-rooms-test\n' in m.UNIT_TEXT
    assert 'RuntimeMaxSec=7200' in m.UNIT_TEXT
    assert 'ReadWritePaths=/home/mcp-rooms-test/data\n' in m.UNIT_TEXT
    assert '[Install]' not in m.UNIT_TEXT
    assert 'ExecStart=/home/mcp-rooms-test/venv/bin/mcp-rooms' in m.UNIT_TEXT
    ast.parse(m.SMOKE)


def test_transient_is_unprivileged_bounded_and_not_an_old_unit():
    args = m.transient('mcp-rooms-build-unit.service', ['/bin/true'], m.HOME)
    assert '--property=User=mcp-rooms-test' in args
    assert '--property=ProtectSystem=strict' in args
    assert '--property=InaccessiblePaths=/root /home/mcp /home/mcp-test /etc/caddy' in args
    assert '--property=RuntimeMaxSec=1200' in args
    assert '--property=MemoryMax=512M' in args
    assert args[-1] == '/bin/true'


def test_preflight_existing_account_stops_before_mutation(monkeypatch):
    monkeypatch.setattr(m.shutil, 'which', lambda x: '/usr/bin/'+x)
    monkeypatch.setattr(m.pwd, 'getpwnam', lambda x: object())
    def forbidden(*a, **kw): raise AssertionError('must not run commands')
    monkeypatch.setattr(m, 'capture', forbidden)
    with pytest.raises(RuntimeError, match='candidate_user_or_group_exists'):
        m.preflight()


def test_invalid_rollback_location_rejected():
    for path in ('state.json', '/tmp/state.json', '/root/unrelated/state.json', '/root/mcp-rooms-install-x/other.json'):
        with pytest.raises(RuntimeError, match='invalid_state_location'): m.load_state(path)


def test_state_write_is_private_and_exclusive(tmp_path):
    path = tmp_path/'state.json'
    m.save_state(path, {'format':1})
    assert path.stat().st_mode & 0o777 == 0o600
    assert json.loads(path.read_text()) == {'format':1}
    m.save_state(path, {'format':2})
    assert json.loads(path.read_text()) == {'format':2}
    path.with_suffix('.new').symlink_to(path)
    with pytest.raises(FileExistsError): m.save_state(path, {'format':3})
    assert json.loads(path.read_text()) == {'format':2}


@pytest.mark.parametrize('created,body', [(False,m.UNIT_TEXT),(True,'changed')])
def test_rollback_refuses_unowned_or_changed_unit(monkeypatch, created, body):
    fake = SimpleNamespace(
        lstat=lambda: SimpleNamespace(st_mode=0o100644,st_uid=0,st_nlink=1),
        read_bytes=lambda:body.encode())
    monkeypatch.setattr(m, 'UNIT_PATH', fake)
    monkeypatch.setattr(m.os.path,'lexists',lambda x:True)
    monkeypatch.setattr(m,'load_state',lambda p:{'unit_created':created})
    def forbidden(*a,**kw): raise AssertionError('must not stop anything')
    monkeypatch.setattr(m,'run',forbidden)
    with pytest.raises(RuntimeError, match='unit_changed_manual_review_required'):
        m.rollback(Path('/unused/state.json'), io.StringIO())


def test_rollback_only_stops_exact_new_unit_preserves_data(monkeypatch):
    calls=[]; state={'unit_created':True,'protected_before':{'same':True}}
    fake=SimpleNamespace(lstat=lambda:SimpleNamespace(st_mode=0o100644,st_uid=0,st_nlink=1),
                         read_bytes=lambda:m.UNIT_TEXT.encode(),unlink=lambda:calls.append('unlink-own-unit'))
    monkeypatch.setattr(m,'UNIT_PATH',fake)
    monkeypatch.setattr(m.os.path,'lexists',lambda x:True)
    monkeypatch.setattr(m,'load_state',lambda p:state)
    monkeypatch.setattr(m,'run',lambda a,*x:calls.append(a))
    monkeypatch.setattr(m,'verify_unit_definition',lambda:None)
    monkeypatch.setattr(m,'save_state',lambda *x:None)
    monkeypatch.setattr(m,'protected',lambda:{'same':True})
    result=m.rollback(Path('/unused/state.json'), io.StringIO())
    assert calls==[['systemctl','stop','mcp-rooms-test.service'],'unlink-own-unit',['systemctl','daemon-reload']]
    assert result['user_home_database_preserved'] and result['protected_services_unchanged']


def test_live_gate_script_against_asgi_only_no_network_or_os_services(tmp_path, monkeypatch, capsys):
    db=tmp_path/'rooms.db'
    with TestClient(create_app(db,m.RESOURCE,True),base_url='https://leonid-mcp.duckdns.org') as client:
        def local_request(req, timeout=None):
            # urllib shim sends to in-process ASGI, never localhost or any network.
            from urllib.parse import urlsplit
            path=urlsplit(req.full_url).path
            response=client.request(req.method,path,content=req.data,headers=dict(req.header_items()))
            if response.status_code>=400:
                raise HTTPError(req.full_url,response.status_code,'synthetic',{},None)
            return Reply(response)
        class Reply(io.BytesIO):
            def __init__(self,response):
                super().__init__(response.content); self.status=response.status_code
        import urllib.request
        monkeypatch.setattr(urllib.request,'urlopen',local_request)
        exec(compile(m.SMOKE.replace('/home/mcp-rooms-test/data/rooms.db',str(db)), '<acceptance>', 'exec'),{})
    assert capsys.readouterr().out.strip()=='LOOPBACK_ACCEPTANCE_PASS'


def test_definition_rejects_dropins_or_other_fragment(monkeypatch):
    for raw in ('FragmentPath=/other/unit\nDropInPaths=',
                'FragmentPath='+str(m.UNIT_PATH)+'\nDropInPaths=/unreviewed.conf'):
        monkeypatch.setattr(m,'capture',lambda args, raw=raw:raw)
        with pytest.raises(RuntimeError, match='new_unit_definition_changed'):
            m.verify_unit_definition()
    monkeypatch.setattr(m,'capture',lambda args:'FragmentPath='+str(m.UNIT_PATH)+'\nDropInPaths=')
    m.verify_unit_definition()
