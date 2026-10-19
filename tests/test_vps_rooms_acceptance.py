"""Pure operator-helper contract tests. Never invoke systemd/Caddy or open a live DB."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

def load(name):
    path = ROOT/'deploy'/name
    spec = importlib.util.spec_from_file_location(name.replace('.','_'), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

@pytest.fixture
def window():
    return load('vps_rooms_window_24h.py')

def test_private_window_has_no_registration_routes(window):
    route = window.make_route('mcp-rooms-route-'+'a'*32)
    text = json.dumps(route)
    assert '/signup' not in text
    assert '/register' not in text
    assert '127.0.0.1:8765' in text
    assert route['match'] == [{'host':['leonid-mcp.duckdns.org'], 'path':['/rooms-test','/rooms-test/*']}]
    assert route['terminal'] is True
    allowed = route['handle'][1]['routes'][1]['match']
    assert allowed == [
        {'path':['/rooms-test/identity','/rooms-test/mcp'],'method':['GET']},
        {'path':['/rooms-test/credentials','/rooms-test/mcp'],'method':['POST']},
        {'path':['/rooms-test/credentials/current','/rooms-test/mcp'],'method':['DELETE']}]

def test_window_override_is_runtime_only_without_signup(window):
    assert str(window.DROPIN_DIR).startswith('/run/systemd/system/')
    assert 'RuntimeMaxSec=90000' in window.DROPIN_TEXT
    assert 'ExecStart=\n' in window.DROPIN_TEXT
    assert '--enable-registration' not in window.DROPIN_TEXT
    assert '--db /home/mcp-rooms-test/data/rooms.db' in window.DROPIN_TEXT

def test_original_unit_hash_matches_pinned_installer(window):
    tree=ast.parse((ROOT/'deploy/vps_install_test.py').read_text())
    text=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)
              and any(isinstance(t,ast.Name) and t.id=='UNIT_TEXT' for t in n.targets))
    assert hashlib.sha256(text.encode()).hexdigest()==window.UNIT_SHA256

def test_cleanup_is_persistent_calendar_not_transient(window):
    state={'marker':'mcp-rooms-route-'+'b'*32,'deadline_calendar':'2026-10-20 22:56:46 UTC'}
    definitions=window.cleanup_definitions(state,Path('/root/mcp-rooms-https-test/state.json'))
    timer=definitions[state['marker']+'-cleanup.timer']
    service=definitions[state['marker']+'-cleanup.service']
    assert 'Persistent=true' in timer
    assert 'OnCalendar=2026-10-20 22:56:46 UTC' in timer
    assert '--remove --state /root/mcp-rooms-https-test/state.json' in service
    assert 'Restart=on-failure' in service

@pytest.mark.parametrize('invalid',['tomorrow','2026-10-20\nExecStart=bad',''])
def test_deadline_injection_rejected(window,invalid):
    with pytest.raises(RuntimeError,match='invalid_deadline'):
        window.cleanup_definitions({'marker':'mcp-rooms-route-'+'c'*32,'deadline_calendar':invalid},Path('/root/x/state.json'))

def test_nonroot_window_stops_before_any_command(window,monkeypatch):
    monkeypatch.setattr(window.os,'geteuid',lambda:1000)
    monkeypatch.setattr(window,'command',lambda *a,**kw:pytest.fail('must not execute'))
    assert window.main(['--open-24h'])==1

def test_window_prefix_collision_stops_without_mutation(window):
    config={'apps':{'http':{'servers':{'srv0':{'listen':[':443'],'routes':[
        {'match':[{'host':[window.HOST]}],'terminal':True,'handle':[]},
        window.make_route('mcp-rooms-route-'+'d'*32)]}}}}}
    with pytest.raises(RuntimeError,match='rooms_prefix_already_present'):
        window.route_list(config)

def test_own_route_removal_preserves_unrelated_config(window):
    marker='mcp-rooms-route-'+'e'*32
    other={'match':[{'host':['other.example']}],'terminal':True,'handle':[]}
    config={'routes':[other,window.make_route(marker)],'other':{'keep':True}}
    assert window.without_marker(config,marker)=={'routes':[other],'other':{'keep':True}}
    assert len(config['routes'])==2

def test_recovery_pins_exact_operator_accepted_window():
    recovery=load('vps_rooms_recovery_drill.py')
    assert recovery.HELPER_SHA256==hashlib.sha256((ROOT/'deploy/vps_rooms_window_24h.py').read_bytes()).hexdigest()

def test_recovery_rejects_unknown_state_location_before_import():
    recovery=load('vps_rooms_recovery_drill.py')
    with pytest.raises(RuntimeError,match='invalid_window_state_location'):
        recovery.verify_helper(Path('/tmp/state.json'))

def test_recovery_queries_only_two_diagnostic_messages():
    recovery=load('vps_rooms_recovery_drill.py')
    assert len(recovery.CANARIES)==2
    assert 'WHERE id IN (?,?)' in recovery.FINGERPRINT
    assert 'credentials' not in recovery.FINGERPRINT
    assert 'digest' in recovery.FINGERPRINT
    assert "'?mode=ro'" in recovery.FINGERPRINT
    ast.parse(recovery.FINGERPRINT)

def test_no_registration_or_revocation_command_in_recovery():
    tree=ast.parse((ROOT/'deploy/vps_rooms_recovery_drill.py').read_text())
    strings=[n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str)]
    assert 'revoke-token' not in strings
    assert 'disable-user' not in strings
    assert 'create-user' not in strings
    assert 'issue-token' not in strings
