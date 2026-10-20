"""Explicit issuance policy and atomic least-privilege self-delegation in CI only."""
from dataclasses import replace
import json
import pytest
from mcp_rooms.identity import IdentityStore, LISTING_SCOPES
from mcp_rooms.store import RoomError
from test_identity import setup, RESOURCE


def test_default_policy_unchanged_and_opt_in_operator_grants(setup):
    store,auth,a,b,ma,ta,mb,tb,now=setup
    with pytest.raises(RoomError,match='invalid_scopes'):auth.issue_token(a,scopes=['listings:read'])
    enabled=IdentityStore(store,RESOURCE,allow_listing_scopes=True)
    meta,raw=enabled.issue_token(a,scopes=sorted(LISTING_SCOPES))
    assert enabled.authenticate(raw).scopes==LISTING_SCOPES
    assert auth.authenticate(raw) is None
    for scopes in (['admin:all'],['listings:read','run_python'],[],['listings:read',1]):
        with pytest.raises(RoomError,match='invalid_scopes'):enabled.issue_token(a,scopes=scopes)


def test_delegate_expiry_and_scope_are_not_amplified(setup):
    store,auth,a,b,ma,ta,mb,tb,now=setup
    now[0]+=10000
    actor=auth.authenticate(ta);meta,raw=auth.delegate_current(actor,ttl_seconds=7776000)
    assert meta['expires_at']==ma['expires_at']
    assert auth.authenticate(raw).scopes==actor.scopes and auth.authenticate(ta)
    assert auth.authenticate(raw).user_id==a and raw!=ta
    with store._db() as db:
        assert raw not in str([dict(r) for r in db.execute('SELECT * FROM credentials')])


@pytest.mark.parametrize('change',['revoke','disable','expiry','resource','scope'])
def test_stale_authenticated_snapshot_cannot_delegate(setup,change):
    store,auth,a,b,ma,ta,mb,tb,now=setup;actor=auth.authenticate(ta)
    if change=='revoke':auth.revoke(ma['credential_id'])
    elif change=='disable':auth.disable(a)
    elif change=='expiry':now[0]=ma['expires_at']*1000
    elif change=='resource':
        with store._db(write=True) as db:db.execute("UPDATE credentials SET resource='https://other.example/mcp' WHERE id=?",(ma['credential_id'],))
    else:
        with store._db(write=True) as db:db.execute("UPDATE credentials SET scopes='[\"rooms:read\"]' WHERE id=?",(ma['credential_id'],))
    with pytest.raises(RoomError,match='insufficient_scope' if change=='scope' else 'authentication_required'):auth.delegate_current(actor)
    with store._db() as db:assert db.execute('SELECT COUNT(*) FROM credentials').fetchone()[0]==2


@pytest.mark.parametrize('value',['not-json','null','{}','[1]','["admin:all"]'])
def test_malformed_persisted_scope_fails_closed(setup,value):
    store,auth,a,b,ma,ta,mb,tb,now=setup;actor=auth.authenticate(ta)
    with store._db(write=True) as db:db.execute('UPDATE credentials SET scopes=? WHERE id=?',(value,ma['credential_id']))
    assert auth.authenticate(ta) is None
    with pytest.raises(RoomError,match='authentication_required'):auth.delegate_current(actor)


def test_forged_snapshot_cannot_gain_persisted_permissions(setup):
    store,auth,a,b,ma,ta,mb,tb,now=setup;actor=auth.authenticate(ta)
    enabled=IdentityStore(store,RESOURCE,allow_listing_scopes=True)
    with pytest.raises(RoomError,match='insufficient_scope'):
        enabled.delegate_current(replace(actor,scopes=actor.scopes|LISTING_SCOPES))
    with pytest.raises(RoomError,match='authentication_required'):
        auth.delegate_current(replace(actor,user_id=b))
