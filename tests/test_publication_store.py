"""Synthetic publication acceptance only: no endpoint, live key or real listing."""
from contextlib import contextmanager
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
import threading
import pytest
from mcp_rooms.publication_store import PublicationStore
from mcp_rooms.publication_preview import PUBLICATION_SCHEMA
from mcp_rooms.media_cleanup import MediaCleanup, GRACE_MS
from mcp_rooms.domain import DomainError
from test_media_stage import env, setup, upload, fails, key, rows
from test_photo_drafts import photos, attach
from test_draft_store import content, create
from test_publication_intent import publisher


@pytest.fixture
def market(photos):
    x = photos
    x.market = PublicationStore(x.editor)
    x.market.initialize()
    x.market.initialize()
    media = upload(x)
    attach(x, [media['media_id']])
    x.media_id = media['media_id']
    return x


def approve(x, preview=None, actor=None, client=None):
    preview = preview or x.market.preview(x.a, x.draft_id)
    return x.market.confirm(actor or x.a,x.draft_id,
        expected_revision=preview['record']['listing']['revision'], preview_digest=preview['digest'],
        consent=True,client_id=client or key())


def publish(x, consent=None, client=None, actor=None):
    consent = consent or approve(x)
    return x.market.publish(actor or x.a,x.draft_id,intent_id=consent['intent_id'],client_id=client or key())


def withdraw(x, revision=1, client=None, actor=None):
    return x.market.withdraw(actor or x.a,x.draft_id,expected_publication_revision=revision,client_id=client or key())


def audit(x):
    with x.store._db() as db:
        return [dict(r) for r in db.execute('SELECT * FROM publication_audit ORDER BY id')]


def test_new_consent_contract_and_atomic_allowlisted_publication(market):
    x = market
    private = x.editor.preview(x.a,x.draft_id)
    preview = x.market.preview(x.a,x.draft_id)
    assert preview['schema'] == PUBLICATION_SCHEMA != private['schema']
    assert preview['public_transport_enabled'] is None and preview['publication_epoch'] == 0
    assert preview['digest'] != private['digest']
    assert preview['card_preview']['published_at'] is None
    assert 'owner' not in preview['card_preview'] and 'user_id' not in preview['card_preview']
    consent = approve(x,preview)
    assert consent['published'] is False and not audit(x)
    fails('listing_unavailable',lambda:x.market.public_get(x.draft_id))
    result = publish(x,consent)
    assert result['state'] == 'active' and result['publication_revision'] == 1
    card = x.market.public_get(x.draft_id)
    assert card['id'] == x.draft_id and card['photos'][0]['media_id'] == x.media_id
    assert card['revision'] == 2 and card['publication_revision'] == 1
    assert set(card) == {'id','revision','publication_revision','title','description','category','kind','modes',
        'locality','region','country','price_minor','currency','category_id','category_path','photos','published_at','expires_at'}
    encoded = json.dumps(card)
    for private_name in ('user_id','owner','credential_id','blob_key','source_hash','intent_id','resource'):
        assert private_name not in encoded
    assert x.market.public_photo(x.draft_id,1,x.media_id).startswith(b'\xff\xd8\xff')
    with x.store._db() as db:
        assert db.execute('SELECT consumed_at FROM publication_consents').fetchone()[0] == x.now[0]
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
    assert [r['action'] for r in audit(x)] == ['publish']
    assert audit(x)[0]['intent_id'] == consent['intent_id']
    assert audit(x)[0]['preview_digest'] == preview['digest']
    assert x.drafts.get(x.a,x.draft_id)['listing']['visibility'] == 'private'


@pytest.mark.parametrize('value',[False,None,1,'yes'])
def test_consent_must_be_explicit_boolean(market,value):
    x=market; preview=x.market.preview(x.a,x.draft_id)
    fails('publication_consent_required',lambda:x.market.confirm(x.a,x.draft_id,expected_revision=2,
        preview_digest=preview['digest'],consent=value,client_id=key()))
    assert not audit(x)


def test_private_intent_and_private_digest_cannot_be_promoted(market):
    x=market; preview=x.editor.preview(x.a,x.draft_id)
    old=x.editor.confirm_intent(x.a,x.draft_id,expected_revision=2,preview_digest=preview['digest'],client_id=key())
    fails('publication_consent_unavailable',lambda:publish(x,old))
    fails('preview_conflict',lambda:approve(x,preview))
    fails('listing_unavailable',lambda:x.market.public_get(x.draft_id))


def test_publish_retry_after_withdraw_does_not_republish(market):
    x=market; consent=approve(x); client=key()
    first=publish(x,consent,client)
    assert publish(x,consent,client) == {**first,'replayed':True}
    withdraw(x)
    assert publish(x,consent,client) == {**first,'replayed':True}
    fails('listing_unavailable',lambda:x.market.public_get(x.draft_id))
    fails('publication_consent_unavailable',lambda:publish(x,consent))
    assert [r['action'] for r in audit(x)] == ['publish','withdraw']


def test_withdraw_retry_does_not_hide_new_publication(market):
    x=market; publish(x); client=key(); removed=withdraw(x,client=client)
    assert removed['publication_revision']==2
    assert publish(x)['publication_revision']==3
    assert withdraw(x,client=client)=={**removed,'replayed':True}
    assert x.market.public_get(x.draft_id)['publication_revision']==3
    fails('listing_unavailable',lambda:x.market.public_photo(x.draft_id,1,x.media_id))
    assert x.market.public_photo(x.draft_id,3,x.media_id)


def test_other_pending_consent_invalid_after_publication_epoch(market):
    x=market; first=approve(x); second=approve(x)
    publish(x,first); withdraw(x)
    fails('publication_consent_unavailable',lambda:publish(x,second))
    assert publish(x)['publication_revision']==3


@pytest.mark.parametrize('operation',['photo_edit','text_edit','archive','stage'])
def test_publication_freezes_private_mutation_paths(market,operation):
    x=market; publish(x)
    actions={
        'photo_edit':lambda:attach(x,[],revision=2),
        'text_edit':lambda:x.editor.update_content(x.a,x.draft_id,content(title='changed'),category_id='toilets',expected_revision=2,client_id=key()),
        'archive':lambda:x.drafts.archive(x.a,x.draft_id,expected_revision=2,client_id=key()),
        'stage':lambda:upload(x,expected_revision=2),
    }
    fails('unpublish_before_edit',actions[operation])
    assert x.market.public_get(x.draft_id)['revision']==2
    withdraw(x)
    if operation!='stage':
        actions[operation]()
        fails('listing_unavailable',lambda:x.market.public_get(x.draft_id))


def test_text_only_editor_is_also_frozen(market):
    x=market
    other=create(x.drafts,x.a)['listing']['id']
    p=x.market.preview(x.a,other)
    c=x.market.confirm(x.a,other,expected_revision=1,preview_digest=p['digest'],consent=True,client_id=key())
    x.market.publish(x.a,other,intent_id=c['intent_id'],client_id=key())
    fails('unpublish_before_edit',lambda:x.drafts.update(x.a,other,content(title='bad'),category_id='toilets',expected_revision=1,client_id=key()))
    assert x.market.public_get(other)['photos']==[]


@pytest.mark.parametrize('change',['text','photo_order','category','expiry','revoke','disable','resource'])
def test_stale_or_unauthorized_consent_never_publishes(market,change):
    x=market; consent=approve(x); expected='publication_consent_unavailable'
    if change=='text':
        x.editor.update_content(x.a,x.draft_id,content(title='changed'),category_id='toilets',expected_revision=2,client_id=key())
    elif change=='photo_order':
        attach(x,[],revision=2)
    elif change=='category':
        with x.store._db(write=True) as db: db.execute("UPDATE market_categories SET title='New name' WHERE id='things'")
    elif change=='expiry': x.now[0]=consent['valid_until']
    elif change=='revoke': x.auth.revoke(x.a.credential_id); expected='authentication_required'
    elif change=='disable':
        with x.store._db(write=True) as db: db.execute('UPDATE users SET disabled=1 WHERE id=?',(x.a.user_id,))
        expected='authentication_required'
    else:
        with x.store._db(write=True) as db: db.execute("UPDATE credentials SET resource='https://wrong.example/mcp' WHERE id=?",(x.a.credential_id,))
        expected='authentication_required'
    fails(expected,lambda:publish(x,consent))
    assert not audit(x)


def test_revocation_during_publish_checksum_is_rechecked(market,monkeypatch):
    x=market; consent=approve(x); read=x.files._read_locked
    def revoke(receipt):
        data=read(receipt); x.auth.revoke(x.a.credential_id); return data
    monkeypatch.setattr(x.files,'_read_locked',revoke)
    fails('authentication_required',lambda:publish(x,consent))
    with x.store._db() as db:
        assert db.execute('SELECT consumed_at FROM publication_consents').fetchone()[0] is None
        assert not db.execute('SELECT * FROM listing_publications').fetchall()
    assert not audit(x)


@pytest.mark.parametrize('kind',['unknown','private','withdrawn','disabled','expired','parent_disabled','tampered','corrupt'])
def test_uniform_public_unavailability(market,kind):
    x=market; lid=x.draft_id
    if kind=='unknown': lid=key()
    if kind not in ('unknown','private'): publish(x)
    if kind=='withdrawn': withdraw(x)
    elif kind=='disabled':
        with x.store._db(write=True) as db: db.execute('UPDATE users SET disabled=1 WHERE id=?',(x.a.user_id,))
    elif kind=='expired': x.now[0]=x.drafts.get(x.a,lid)['listing']['expires_at']
    elif kind=='parent_disabled':
        with x.store._db(write=True) as db: db.execute("UPDATE market_categories SET active=0 WHERE id='things'")
    elif kind=='tampered':
        with x.store._db(write=True) as db: db.execute("UPDATE market_drafts SET content=REPLACE(content,'Унитаз','Other') WHERE id=?",(lid,))
        # Fixture title is independent of localization; change a canonical field.
        with x.store._db(write=True) as db:
            row=db.execute('SELECT content FROM market_drafts WHERE id=?',(lid,)).fetchone(); data=json.loads(row[0]); data['title']='Tampered'
            db.execute('UPDATE market_drafts SET content=? WHERE id=?',(json.dumps(data),lid))
    elif kind=='corrupt': next(x.root.iterdir()).write_bytes(b'broken')
    fails('listing_unavailable',lambda:x.market.public_get(lid))
    fails('listing_unavailable',lambda:x.market.public_photo(lid,1,x.media_id))


def test_withdraw_during_public_file_read_is_rechecked(market,monkeypatch):
    x=market; publish(x); read=x.files._read_locked
    def remove(receipt):
        data=read(receipt); withdraw(x); return data
    monkeypatch.setattr(x.files,'_read_locked',remove)
    fails('listing_unavailable',lambda:x.market.public_photo(x.draft_id,1,x.media_id))


def test_foreign_user_and_missing_scope_denied(market):
    x=market; b=publisher(x.store,x.b)
    fails('draft_unavailable',lambda:x.market.preview(b,x.draft_id))
    consent=approve(x)
    fails('draft_unavailable',lambda:publish(x,consent,actor=b))
    weak=replace(x.a,scopes=frozenset({'listings:read','listings:write'}))
    fails('insufficient_scope',lambda:publish(x,consent,actor=weak))
    publish(x,consent)
    fails('publication_unavailable',lambda:withdraw(x,actor=b))
    fails('insufficient_scope',lambda:withdraw(x,actor=weak))


def test_receipt_failure_rolls_back_consumption_publication_and_audit(market,monkeypatch):
    x=market; consent=approve(x); original=x.drafts._receipt
    def fail(*a,**kw): raise sqlite3.OperationalError('synthetic receipt fault')
    with monkeypatch.context() as patch:
        patch.setattr(x.drafts,'_receipt',fail)
        with pytest.raises(sqlite3.OperationalError): publish(x,consent)
    with x.store._db() as db:
        assert not db.execute('SELECT * FROM listing_publications').fetchall()
        assert db.execute('SELECT consumed_at FROM publication_consents').fetchone()[0] is None
    assert not audit(x)
    assert publish(x,consent)['state']=='active'


def test_audit_failure_rolls_back_all_changes(market,monkeypatch):
    x=market; consent=approve(x)
    def fail(*a,**kw): raise sqlite3.OperationalError('synthetic audit fault')
    with monkeypatch.context() as patch:
        patch.setattr(x.market,'_audit',fail)
        with pytest.raises(sqlite3.OperationalError): publish(x,consent)
    with x.store._db() as db:
        assert not db.execute('SELECT * FROM listing_publications').fetchall()
        assert db.execute('SELECT consumed_at FROM publication_consents').fetchone()[0] is None
    assert publish(x,consent)['state']=='active'


def test_concurrent_publish_consumes_once(market):
    x=market; consent=approve(x); barrier=threading.Barrier(2)
    def action(_):
        barrier.wait()
        try:return publish(x,consent)
        except DomainError as e:return e.code
    with ThreadPoolExecutor(max_workers=2) as pool: result=list(pool.map(action,[1,2]))
    assert sum(isinstance(r,dict) for r in result)==1
    assert result.count('unpublish_before_edit')==1 and len(audit(x))==1


def test_active_photos_survive_staging_ttl_and_cleanup_after_expiry(market):
    x=market; publish(x); x.now[0]+=600000+GRACE_MS
    cleanup=MediaCleanup(x.service)
    assert cleanup.plan()['candidates']==[]
    assert x.market.public_get(x.draft_id)
    x.now[0]=x.drafts.get(x.a,x.draft_id)['listing']['expires_at']+GRACE_MS
    cleanup.apply(cleanup.plan())
    assert rows(x)[0]['cleanup_state']=='purged'
    fails('listing_unavailable',lambda:x.market.public_photo(x.draft_id,1,x.media_id))


def test_partial_namespace_is_refused_by_editors_and_initializer(market):
    x=market
    with x.store._db(write=True) as db: db.execute('DROP TABLE publication_audit')
    fails('unsupported_publication_schema',x.market.initialize)
    fails('unsupported_publication_schema',lambda:attach(x,[],revision=2))


def test_initialize_failure_is_atomic_and_room_identifiers_unchanged(photos,monkeypatch):
    x=photos; market=PublicationStore(x.editor); original=x.store._db
    with original() as db:
        identifiers=tuple(db.execute('PRAGMA '+q).fetchone()[0] for q in ('application_id','user_version'))
    class Proxy:
        def __init__(self,db): self.db=db
        def execute(self,sql,*a):
            if 'CREATE TABLE publication_audit' in sql:raise sqlite3.OperationalError('synthetic DDL fault')
            return self.db.execute(sql,*a)
    @contextmanager
    def faulty(*a,**kw):
        with original(*a,**kw) as db:yield Proxy(db)
    with monkeypatch.context() as patch:
        patch.setattr(x.store,'_db',faulty)
        with pytest.raises(sqlite3.OperationalError):market.initialize()
    with original() as db:
        assert not db.execute("SELECT name FROM sqlite_master WHERE name IN ('publication_schema','listing_publications','publication_consents','publication_audit')").fetchall()
    market.initialize()
    with original() as db:
        assert tuple(db.execute('PRAGMA '+q).fetchone()[0] for q in ('application_id','user_version'))==identifiers
        assert not db.execute('PRAGMA foreign_key_check').fetchall()


def test_withdraw_audit_failure_rolls_back_state_and_receipt(market,monkeypatch):
    x=market; publish(x); command=key()
    def fail(*a,**kw):raise sqlite3.OperationalError('synthetic withdrawal audit fault')
    with monkeypatch.context() as patch:
        patch.setattr(x.market,'_audit',fail)
        with pytest.raises(sqlite3.OperationalError):withdraw(x,client=command)
    assert x.market.public_get(x.draft_id)['publication_revision']==1
    with x.store._db() as db:
        assert not db.execute('SELECT * FROM market_commands WHERE client_id=?',(command,)).fetchall()
    assert withdraw(x,client=command)['publication_revision']==2
    assert [r['action'] for r in audit(x)]==['publish','withdraw']


def test_withdraw_remains_available_when_category_or_photo_is_broken(market):
    x=market; publish(x)
    with x.store._db(write=True) as db:db.execute("UPDATE market_categories SET active=0 WHERE id='things'")
    next(x.root.iterdir()).write_bytes(b'broken')
    assert withdraw(x)['state']=='withdrawn'
    fails('listing_unavailable',lambda:x.market.public_get(x.draft_id))


def test_credential_revocation_does_not_erase_user_publication(market):
    x=market; publish(x); x.auth.revoke(x.a.credential_id)
    assert x.market.public_get(x.draft_id)['id']==x.draft_id
    fails('authentication_required',lambda:withdraw(x))


def test_unselected_photo_is_never_public_by_opaque_id(market):
    x=market
    unselected=upload(x,expected_revision=2,payload=b'another-synthetic')
    publish(x)
    fails('listing_unavailable',lambda:x.market.public_photo(x.draft_id,1,unselected['media_id']))
    assert x.service.read(x.a,unselected['media_id'])


def test_command_capacity_failure_does_not_consume_consent(market):
    x=market; consent=approve(x)
    with x.store._db() as db:used=db.execute('SELECT COUNT(*) FROM market_commands WHERE user_id=?',(x.a.user_id,)).fetchone()[0]
    x.drafts.limits=replace(x.drafts.limits,commands_per_owner=used)
    fails('owner_command_capacity',lambda:publish(x,consent))
    with x.store._db() as db:
        assert db.execute('SELECT consumed_at FROM publication_consents').fetchone()[0] is None
        assert not db.execute('SELECT * FROM listing_publications').fetchall()
    assert not audit(x)
