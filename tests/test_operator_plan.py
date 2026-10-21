"""Pure proposal tests, not host lifecycle tests. Actions only."""
from copy import deepcopy
import json
from pathlib import Path
import runpy
import pytest
ROOT=Path(__file__).resolve().parents[1]
m=runpy.run_path(str(ROOT/'tools/operator_plan.py'))
Error=m['PlanError']


def observations():
    return {'format':'mcp-rooms/host-observation/v1',
            'target':{'python':'3.12','system':'Linux','machine':'x86_64'},
            'user_absent':True,'group_absent':True,
            'paths_absent':{p:True for p in m['TARGETS']},'port_free':True,
            'systemd_available':True,'python312_venv_available':True,
            'landlock_abi':3,'free_bytes':2*1024**3,'available_memory_bytes':1024**3}


def proposal(monkeypatch,value=None,**kw):
    # No false fixture claim: real wheelhouse verifier integration is a separate job.
    report={'ok':True,'kind':'locked-wheelhouse-not-vps-installer'}
    called=[]
    def verifier(*args,**kwargs):called.append((args,kwargs));return report
    monkeypatch.setattr(m['build_plan'].__globals__['runpy'],'run_path',lambda path:{'verify':verifier})
    result=m['build_plan'](Path('/synthetic/bundle'),kw.get('sha','a'*40),kw.get('lock','b'*64),kw.get('resource','https://candidate.invalid/rooms-test/mcp'),observations() if value is None else value)
    assert called[0][1]=={} # No allow_seed override.
    return result


def test_proposal_is_explicitly_not_installation(monkeypatch):
    value=observations();before=deepcopy(value)
    result=proposal(monkeypatch,value)
    assert value==before
    assert result['host_probe_performed'] is False and result['install_authorized'] is False
    assert result['runtime_resources_accepted'] is False
    assert result['identity']=={'user':'mcp-rooms-candidate','group':'mcp-rooms-candidate','unit':'mcp-rooms-candidate.service','boot_enabled':False}
    assert result['network']['listen_host']=='127.0.0.1' and result['network']['listen_port']==8766
    assert result['network']['create_https_route'] is False
    assert result['install_policy']['network_fallback'] is False
    assert result['layout']['fresh_profile']=='/var/lib/mcp-rooms-candidate/owner-first'
    assert [x['id'] for x in result['steps']]==['preflight','offline_install','bootstrap','loopback_start','health','stop','rollback']
    assert 'stop new candidate only' in result['steps'][-1]['requirements'][0]
    assert len(result['plan_sha256'])==64
    assert result==proposal(monkeypatch,value)


@pytest.mark.parametrize('field',['user_absent','group_absent','port_free','systemd_available','python312_venv_available'])
@pytest.mark.parametrize('value',[False,1])
def test_conflict_or_truthy_nonbool_not_accepted(monkeypatch,field,value):
    o=observations();o[field]=value
    with pytest.raises(Error,match='operator_host_prerequisite_refused'):proposal(monkeypatch,o)


@pytest.mark.parametrize('change',['path','missing_path','extra_path','landlock','disk','memory_type','unknown','missing','target'])
def test_observation_failures(monkeypatch,change):
    o=observations()
    if change=='path':o['paths_absent'][m['TARGETS'][0]]=False
    elif change=='missing_path':o['paths_absent'].pop(m['TARGETS'][0])
    elif change=='extra_path':o['paths_absent']['/home/mcp']=True
    elif change=='landlock':o['landlock_abi']=2
    elif change=='disk':o['free_bytes']=2*1024**3-1
    elif change=='memory_type':o['available_memory_bytes']=True
    elif change=='unknown':o['secret']='synthetic forbidden key'
    elif change=='missing':del o['user_absent']
    elif change=='target':o['target']['machine']='aarch64'
    with pytest.raises(Error):proposal(monkeypatch,o)


@pytest.mark.parametrize('resource',['http://candidate.invalid/rooms-test/mcp','https://u:p@candidate.invalid/rooms-test/mcp',
 'https://candidate.invalid:443/rooms-test/mcp','https://candidate.invalid/rooms-test/mcp?q=x',
 'https://candidate.invalid/rooms-test/mcp#x','https://candidate.invalid/a/../rooms/mcp',
 'https://candidate.invalid/a%2fb/mcp','https://candidate.invalid/rooms-test/mcp\n',
 'https://candidate.invalid/room\\s/mcp','https://Candidate.invalid/rooms-test/mcp',
 'https://candidate.invalid//mcp','https://candidate.invalid/rooms-test/stop'])
def test_resource_injection_and_noncanonical_urls_refused(monkeypatch,resource):
    with pytest.raises(Error,match='operator_invalid_resource'):proposal(monkeypatch,resource=resource)


@pytest.mark.parametrize('kw',[{'sha':'a'*39},{'lock':'b'*63},{'sha':'A'*40}])
def test_trust_anchor_malformed_refused(monkeypatch,kw):
    with pytest.raises(Error):proposal(monkeypatch,**kw)


def test_bundle_verification_refusal_not_downgraded(monkeypatch):
    def refuse(*a,**kw):raise ValueError('synthetic mismatch')
    monkeypatch.setattr(m['build_plan'].__globals__['runpy'],'run_path',lambda p:{'verify':refuse})
    with pytest.raises(ValueError,match='synthetic mismatch'):
        m['build_plan'](Path('/synthetic/bundle'),'a'*40,'b'*64,'https://candidate.invalid/rooms-test/mcp',observations())


def test_low_or_unknown_ram_does_not_claim_capacity_acceptance(monkeypatch):
    o=observations();o['available_memory_bytes']=0
    assert proposal(monkeypatch,o)['runtime_resources_accepted'] is False
