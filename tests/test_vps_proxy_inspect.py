"""Pure sanitizer tests only; no real Caddy, network, root snapshot or VPS access."""
import importlib.util
import json
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('vps_proxy_inspect',Path(__file__).parents[1]/'deploy/vps_proxy_inspect.py')
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


def test_sanitizer_keeps_structure_not_auth_values_or_unknown_paths():
    config={'logging':{},'apps':{'http':{'servers':{'secret-server-name':{'logs':{},'routes':[
        {'match':[{'host':[m.HOST],'header':{'X-Api-Key':['SECRET_VALUE']},'path':['/test/*','/private-secret-path']}],
         'terminal':True,'handle':[{'handler':'subroute','routes':[
            {'handle':[{'handler':'rewrite','strip_path_prefix':'/test'},
                       {'handler':'reverse_proxy','upstreams':[{'dial':'127.0.0.1:3002'},{'dial':'external-secret-host:80'}]}]},
            {'handle':[{'handler':'static_response','status_code':401,'body':'SECRET_BODY'}]}]}]}]}}}}}
    result=m.summarize(config); text=json.dumps(result)
    for private in ('SECRET_VALUE','SECRET_BODY','private-secret-path','external-secret-host','secret-server-name'):
        assert private not in text
    assert result['servers_with_expected_host']==1
    assert not result['rooms_prefix_already_referenced']
    assert '3002' in text and '/test/*' in text and '401' in text
    assert result['logging_configuration_present'] and not result['log_redaction_verified']


def test_collision_and_output_bounds_are_explicit():
    config={'apps':{'http':{'servers':{'x':{'routes':[
        {'match':[{'path':['/rooms-test/*']}],'handle':[{'handler':'reverse_proxy','upstreams':[{'dial':'localhost:8765'}]}]}
    ]*60}}}}}
    result=m.summarize(config)
    assert result['rooms_prefix_already_referenced'] and result['truncated']
    assert len(result['routes'])==m.MAX_NODES


def test_paths_ports_and_redirects_never_export_unknown_strings():
    assert m.safe_path('/rooms-test/signup')=='/rooms-test/signup'
    assert m.safe_path('/rooms-test/register?secret=bad')=='<other-path>'
    assert m.safe_path('/private')=='<other-path>'
    assert m.safe_path({'unexpected':'SECRET'})=='<other-path>'
    assert m.upstreams([{'dial':'[::1]:8765'},{'dial':'host-secret:443'}])==([8765],True)
    assert m.NoRedirect().redirect_request(None,None,302,'',{},'https://external.invalid') is None


def test_nonroot_does_not_inspect_or_create_files(monkeypatch,capsys):
    monkeypatch.setattr(m.os,'geteuid',lambda:1000)
    def forbidden(*a,**kw):raise AssertionError('no operator work in CI')
    monkeypatch.setattr(m,'command',forbidden)
    monkeypatch.setattr(m,'build_opener',forbidden)
    monkeypatch.setattr(m.tempfile,'mkdtemp',forbidden)
    assert m.main()==1
    assert 'operator_root_console_required' in capsys.readouterr().out
