"""Pure rendering negatives; real systemd tests live in isolated Actions only."""
from pathlib import Path
import runpy
import pytest

ROOT=Path(__file__).resolve().parents[1]
render=runpy.run_path(str(ROOT/'tools/operator_unit.py'))['render']
SHA='a'*40
RESOURCE='https://example.invalid/rooms-candidate/mcp'


def test_fixed_unit_identity_and_source_paths():
    value=render(SHA,RESOURCE)
    assert 'User=mcp-rooms-candidate\nGroup=mcp-rooms-candidate\n' in value
    assert '/opt/mcp-rooms-candidate/releases/'+SHA+'/venv/bin/python -I -m mcp_rooms.test_candidate serve' in value
    assert '--state /var/lib/mcp-rooms-candidate/owner-first --resource '+RESOURCE in value
    assert 'WorkingDirectory=/opt/mcp-rooms-candidate/releases/'+SHA in value
    assert 'ExecStartPre=' not in value and '[Install]' not in value and 'WantedBy=' not in value


@pytest.mark.parametrize('directive',[
    'KillMode=control-group','SendSIGKILL=yes','TimeoutStopSec=10s','RuntimeMaxSec=2h',
    'MemoryAccounting=yes','CPUAccounting=yes','TasksAccounting=yes','MemoryMax=1G',
    'MemorySwapMax=0','TasksMax=64','CPUQuota=100%','Restart=no','UMask=0077',
    'NoNewPrivileges=yes','CapabilityBoundingSet=','AmbientCapabilities=',
    'ProtectSystem=strict','ProtectHome=yes','ReadWritePaths=/var/lib/mcp-rooms-candidate',
    'ReadOnlyPaths=/opt/mcp-rooms-candidate','StandardOutput=null','StandardError=null'])
def test_review_safety_directives(directive):
    assert directive+'\n' in render(SHA,RESOURCE)


@pytest.mark.parametrize('source',['', 'a'*39,'A'*40,'g'*40,'a'*40+'\n',None,23])
def test_source_injection_refused(source):
    with pytest.raises(ValueError):render(source,RESOURCE)


@pytest.mark.parametrize('resource',[
    'http://example.invalid/a/mcp','https://example.invalid/a/mcp\nExecStart=/bin/sh',
    'https://example.invalid/a%20/mcp','https://u:p@example.invalid/a/mcp',
    'https://example.invalid/a/mcp?key=secret','https://example.invalid:443/a/mcp',
    'https://example.invalid/a/mcp#x',None])
def test_resource_injection_refused(resource):
    with pytest.raises(Exception):render(SHA,resource)


def test_renderer_no_host_or_credential_operations(monkeypatch):
    import os,subprocess,socket
    def deny(*a,**k):raise AssertionError('unexpected host operation')
    for name in ('run','Popen'):monkeypatch.setattr(subprocess,name,deny)
    monkeypatch.setattr(socket,'socket',deny)
    monkeypatch.setattr(os,'system',deny)
    assert render(SHA,RESOURCE)==render(SHA,RESOURCE)
