"""Pure contract fixtures; not HTTP/storage/publication acceptance."""
from dataclasses import replace
import pytest
from mcp_rooms.identity import Principal
from mcp_rooms.listing_contract import ListingContent, create_draft, change_status, public_projection
from mcp_rooms.store import RoomError

A = Principal('11111111-1111-4111-8111-111111111111', 'a'*32,
              frozenset({'listings:write', 'listings:publish'}))
B = replace(A, user_id='22222222-2222-4222-8222-222222222222')
ID = '33333333-3333-4333-8333-333333333333'


def content(**kw):
    fields = dict(title='Вещь', description='Честное описание',
                  category='things', kind='offer', modes=('shipping',))
    return ListingContent(**{**fields, **kw})


def test_worldwide_not_bound_to_city_and_draft_never_public():
    draft = create_draft(A, ID, content(), 1000)
    assert draft.content.country == '' and draft.content.locality == ''
    assert public_projection(draft, 1001) is None
    active = change_status(A, draft, 'active', expected_revision=1, now=1001, publish_consent=True)
    view = public_projection(active, 1001)
    assert view['id'] == ID and view['revision'] == 2
    assert 'owner' not in view and 'credential_id' not in view and 'scopes' not in view
    assert public_projection(active, active.expires_at) is None


@pytest.mark.parametrize('changes', [
    {'price_minor': True, 'currency': 'RUB'}, {'price_minor': -1, 'currency': 'RUB'},
    {'price_minor': 1.5, 'currency': 'RUB'}, {'currency': 'RUB'},
    {'price_minor': 100, 'currency': 'rub'}, {'media_ids': ('https://evil.example/x',)},
    {'media_ids': (ID, ID)}, {'locality': 123},
])
def test_invalid_content(changes):
    with pytest.raises(RoomError):
        content(**changes)


def test_categories_modes_and_location():
    with pytest.raises(RoomError):
        ListingContent('A', 'B', 'things', 'offer', ('pickup',))
    for bad in (('shipping', 'shipping'), ('shell',), [], (), ('shipping', 3)):
        with pytest.raises(RoomError):
            ListingContent('A', 'B', 'things', 'offer', bad)
    c = ListingContent('A', 'B', 'services', 'request', ('online',))
    assert c.locality == ''


def test_price_minor_and_unicode():
    c = content(price_minor=0, currency='RUB', locality='  Казань  ')
    assert c.price_minor == 0 and c.locality == 'Казань'


def test_scope_consent_owner_cas_and_lifecycle():
    draft = create_draft(A, ID, content(), 1000)
    for p, rev, consent, error in (
        (B, 1, True, 'not_listing_owner'), (A, 2, True, 'revision_conflict'),
        (A, 1, False, 'publication_consent_required'), (A, 1, 1, 'publication_consent_required'),
        (replace(A, scopes=frozenset({'rooms:write'})), 1, True, 'insufficient_scope')):
        with pytest.raises(RoomError, match=error):
            change_status(p, draft, 'active', expected_revision=rev, now=1001, publish_consent=consent)
    active = change_status(A, draft, 'active', expected_revision=1, now=1001, publish_consent=True)
    paused = change_status(A, active, 'paused', expected_revision=2, now=1002)
    assert public_projection(paused, 1002) is None
    done = change_status(A, paused, 'fulfilled', expected_revision=3, now=1003)
    assert public_projection(done, 1003) is None
    with pytest.raises(RoomError):
        change_status(A, done, 'active', expected_revision=4, now=1004, publish_consent=True)
    with pytest.raises(RoomError):
        change_status(A, active, 'blocked', expected_revision=2, now=1003)


def test_expiry_immutability_and_input_bounds():
    draft = create_draft(A, ID, content(), 1000, lifetime_ms=60000)
    assert draft.revision == 1 and draft.status == 'draft'
    for now in (999, draft.expires_at, True):
        with pytest.raises(RoomError):
            change_status(A, draft, 'active', expected_revision=1, now=now, publish_consent=True)
    with pytest.raises(RoomError):
        create_draft(None, ID, content(), 1000)
    with pytest.raises(RoomError):
        create_draft(A, ID, content(), 1000, lifetime_ms=0)
    with pytest.raises(RoomError):
        content(title='x'*121)
    with pytest.raises(RoomError):
        replace(draft, visibility='public')


def test_untrusted_text_is_not_executed_or_treated_as_markup():
    # Data retains exact code points for a future autoescaping template.
    c = content(description='<script>alert(1)</script>')
    draft = create_draft(A, ID, c, 1000)
    active = change_status(A, draft, 'active', expected_revision=1, now=1001, publish_consent=True)
    assert public_projection(active, 1002)['description'] == '<script>alert(1)</script>'
