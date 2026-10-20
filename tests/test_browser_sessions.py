"""CI-only synthetic session core acceptance; no web login, key delivery or HTTP."""
from dataclasses import replace
import json
from concurrent.futures import ThreadPoolExecutor
import pytest
from mcp_rooms import browser_sessions as bs
from mcp_rooms.browser_sessions import BrowserSessions
from mcp_rooms.domain import DomainError
from mcp_rooms.identity import IdentityStore
from test_draft_store import setup


@pytest.fixture
def browser(setup):
    store,auth,drafts,a,b,now=setup
    sessions=BrowserSessions(drafts);sessions.initialize()
    return sessions,auth,a,b,now


def fails(code,fn):
    with pytest.raises(DomainError) as exc:fn()
    assert exc.value.code==code


def test_digest_only_independent_browser_token_and_least_privilege(browser):
    s,auth,a,b,now=browser
    issued=s.create(a)
    assert issued.context.principal.scopes==frozenset({'listings:read'})
    assert auth.authenticate(issued.cookie) is None
    assert issued.cookie not in repr(issued) and issued.context.csrf_token not in repr(issued)
    with s.store._db() as db:
        row=dict(db.execute('SELECT * FROM browser_sessions').fetchone())
        assert issued.cookie not in json.dumps(row) and issued.context.csrf_token not in json.dumps(row)
    resolved=s.resolve(issued.cookie)
    assert resolved==issued.context and resolved.principal.user_id==a.user_id
    assert b.user_id != resolved.principal.user_id


def test_schema_is_explicit_and_room_identity_unchanged(setup):
    store,auth,drafts,a,b,now=setup
    s=BrowserSessions(drafts)
    fails('browser_migration_required',lambda:s.create(a))
    with store._db() as db:
        identity=tuple(db.execute('PRAGMA application_id').fetchone())
    s.initialize();s.initialize()
    with store._db() as db:
        assert tuple(db.execute('PRAGMA application_id').fetchone())==identity
        db.execute('SELECT * FROM rooms')
    with store._db(write=True) as db:db.execute('UPDATE browser_session_schema SET version=99')
    fails('unsupported_browser_schema',s.initialize)


@pytest.mark.parametrize('scopes',[[],['rooms:read'],['admin:write'],['listings:read','listings:read'],['unknown'],True,'listings:read'])
def test_invalid_scope_requests(browser,scopes):
    s,auth,a,b,now=browser
    fails('invalid_browser_scopes',lambda:s.create(a,scopes=scopes))


def test_no_scope_elevation_from_snapshot_or_stored_grant(browser):
    s,auth,a,b,now=browser
    fails('insufficient_scope',lambda:s.create(a,scopes=['listings:publish']))
    forged=replace(a,scopes=a.scopes|{'listings:publish'})
    fails('insufficient_scope',lambda:s.create(forged,scopes=['listings:publish']))
    fails('authentication_required',lambda:s.create(replace(a,user_id=b.user_id)))
    fails('authentication_required',lambda:s.create(None))


@pytest.mark.parametrize('ttl',[False,0,59,3601,'3600'])
def test_lifetime_input(browser,ttl):
    s,auth,a,b,now=browser
    fails('invalid_browser_lifetime',lambda:s.create(a,ttl_seconds=ttl))


def test_parent_expiry_caps_absolute_lifetime(browser):
    s,auth,a,b,now=browser
    with s.store._db(write=True) as db:
        db.execute('UPDATE credentials SET expires_at=? WHERE id=?',(now[0]//1000+70,a.credential_id))
    issued=s.create(a)
    assert issued.context.expires_at==now[0]+70000
    now[0]+=70000
    fails('browser_session_required',lambda:s.resolve(issued.cookie))


@pytest.mark.parametrize('change',['revoke','disable','expiry','resource','scope','malformed_scope'])
def test_parent_changes_invalidate_existing_sessions(browser,change):
    s,auth,a,b,now=browser;issued=s.create(a)
    with s.store._db(write=True) as db:
        if change=='revoke':db.execute('UPDATE credentials SET revoked=1 WHERE id=?',(a.credential_id,))
        elif change=='disable':db.execute('UPDATE users SET disabled=1 WHERE id=?',(a.user_id,))
        elif change=='expiry':db.execute('UPDATE credentials SET expires_at=0 WHERE id=?',(a.credential_id,))
        elif change=='resource':db.execute("UPDATE credentials SET resource='https://other.example/mcp' WHERE id=?",(a.credential_id,))
        elif change=='scope':db.execute("UPDATE credentials SET scopes='[\"listings:write\"]' WHERE id=?",(a.credential_id,))
        else:db.execute("UPDATE credentials SET scopes='broken' WHERE id=?",(a.credential_id,))
    with pytest.raises(DomainError):s.resolve(issued.cookie)


def test_idle_extension_never_extends_absolute_expiry(browser):
    s,auth,a,b,now=browser;issued=s.create(a);deadline=issued.context.expires_at
    for i in range(1,5):
        now[0]+=800000
        assert s.resolve(issued.cookie).expires_at==deadline
    now[0]=deadline
    fails('browser_session_required',lambda:s.resolve(issued.cookie))


def test_idle_exact_boundary_and_rollback(browser):
    s,auth,a,b,now=browser;issued=s.create(a)
    now[0]+=bs.IDLE_MS
    fails('browser_session_required',lambda:s.resolve(issued.cookie))
    fresh=s.create(a);now[0]-=1
    fails('browser_session_required',lambda:s.resolve(fresh.cookie))


def test_csrf_per_session_required_for_mutation_without_touch_on_failure(browser):
    s,auth,a,b,now=browser;one=s.create(a);two=s.create(a)
    initial=now[0];now[0]+=1000
    for csrf in (None,'',one.cookie,two.context.csrf_token,one.context.csrf_token.upper()):
        fails('browser_csrf_required',lambda:s.resolve(one.cookie,mutating=True,csrf_token=csrf))
    with s.store._db() as db:
        assert db.execute('SELECT last_seen FROM browser_sessions WHERE id=?',(one.context.session_id,)).fetchone()[0]==initial
    result=s.resolve(one.cookie,mutating=True,csrf_token=one.context.csrf_token)
    assert result.csrf_token==one.context.csrf_token
    fails('invalid_browser_operation',lambda:s.resolve(one.cookie,mutating='false'))


def test_logout_is_idempotent_session_only_and_after_parent_revoked(browser):
    s,auth,a,b,now=browser;one=s.create(a);two=s.create(a)
    fails('browser_csrf_required',lambda:s.logout(one.cookie,csrf_token=two.context.csrf_token))
    assert s.logout(one.cookie,csrf_token=one.context.csrf_token)['revoked']
    assert s.logout(one.cookie,csrf_token=one.context.csrf_token)['revoked']
    fails('browser_session_required',lambda:s.resolve(one.cookie))
    assert s.resolve(two.cookie).principal==two.context.principal
    with s.store._db() as db:
        assert db.execute('SELECT revoked FROM credentials WHERE id=?',(a.credential_id,)).fetchone()[0]==0
    auth.revoke(a.credential_id)
    assert s.logout(two.cookie,csrf_token=two.context.csrf_token)['revoked']


@pytest.mark.parametrize('raw',[None,'','bs1_bad','rm1_'+'0'*32+'.'+'x'*43,'x'*1000])
def test_malformed_and_foreign_namespace(browser,raw):
    s,auth,a,b,now=browser
    fails('browser_session_required',lambda:s.resolve(raw))


def test_tamper_cookie_resource_audience_and_stored_scopes(browser):
    s,auth,a,b,now=browser;issued=s.create(a)
    raw=issued.cookie[:-1]+('x' if issued.cookie[-1]!='x' else 'y')
    fails('browser_session_required',lambda:s.resolve(raw))
    for column,value in [('resource','https://other.example/mcp'),('audience','mcp-rooms/admin/v1'),('scopes','["rooms:write"]')]:
        fresh=s.create(a)
        with s.store._db(write=True) as db:
            db.execute('UPDATE browser_sessions SET '+column+'=? WHERE id=?',(value,fresh.context.session_id))
        fails('browser_session_required',lambda:s.resolve(fresh.cookie))


def test_caps_count_expired_and_revoked_rows(browser,monkeypatch):
    s,auth,a,b,now=browser;monkeypatch.setattr(bs,'MAX_OWNER_ROWS',2)
    one=s.create(a);s.logout(one.cookie,csrf_token=one.context.csrf_token);s.create(a)
    fails('browser_owner_session_capacity',lambda:s.create(a))
    s.create(b);monkeypatch.setattr(bs,'MAX_ROWS',3)
    fails('browser_session_capacity',lambda:s.create(b))


def test_concurrent_creation_owner_cap_atomic(browser,monkeypatch):
    s,auth,a,b,now=browser;monkeypatch.setattr(bs,'MAX_OWNER_ROWS',2)
    def attempt(_):
        try:return s.create(a).context.session_id
        except DomainError as e:return e.code
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(attempt,range(8)))
    assert results.count('browser_owner_session_capacity')==6
    assert len({r for r in results if r!='browser_owner_session_capacity'})==2
