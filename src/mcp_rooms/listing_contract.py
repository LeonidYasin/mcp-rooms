"""Pure next-alpha listing contract. NOT registered in MCP/HTTP or persisted yet.

Callers must authenticate/recheck revocation before every command. This module
cannot verify credentials, media ownership or category availability; a future
transactional service must do those checks. Existing room scopes are unchanged.
"""
from dataclasses import dataclass, replace
import re
from .domain import Principal, DomainError as RoomError, identifier as _id, text as _text

MODES = frozenset({'pickup', 'shipping', 'online'})
CATEGORIES = frozenset({'things', 'services', 'rides', 'delivery', 'other'})
STATUSES = frozenset({'draft', 'active', 'paused', 'fulfilled', 'archived', 'blocked'})
MAX_LIFETIME_MS = 90 * 86400000


def _integer(value, minimum, maximum, code):
    if type(value) is not int or not minimum <= value <= maximum:
        raise RoomError(code)
    return value


def _optional_text(value, maximum):
    return '' if value == '' else _text(value, maximum)


@dataclass(frozen=True)
class ListingContent:
    title: str
    description: str
    category: str
    kind: str
    modes: tuple[str, ...]
    locality: str = ''
    region: str = ''
    country: str = ''
    price_minor: int | None = None
    currency: str | None = None
    media_ids: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, 'title', _text(self.title, 120))
        object.__setattr__(self, 'description', _text(self.description, 6000))
        if type(self.category) is not str or self.category not in CATEGORIES:
            raise RoomError('invalid_category')
        if type(self.kind) is not str or self.kind not in {'request', 'offer'}:
            raise RoomError('invalid_listing_kind')
        if (type(self.modes) is not tuple or not 1 <= len(self.modes) <= 3
                or any(type(x) is not str or x not in MODES for x in self.modes)
                or len(set(self.modes)) != len(self.modes)):
            raise RoomError('invalid_fulfilment_modes')
        for field in ('locality', 'region', 'country'):
            object.__setattr__(self, field, _optional_text(getattr(self, field), 100))
        if 'pickup' in self.modes and not self.locality:
            raise RoomError('pickup_locality_required')
        if self.price_minor is None:
            if self.currency is not None:
                raise RoomError('currency_without_price')
        else:
            _integer(self.price_minor, 0, 10**14, 'invalid_price')
            # Syntax only, not an ISO catalogue or currency precision resolver.
            if not isinstance(self.currency, str) or not re.fullmatch('[A-Z]{3}', self.currency):
                raise RoomError('invalid_currency')
        if type(self.media_ids) is not tuple or len(self.media_ids) > 8:
            raise RoomError('invalid_media')
        for item in self.media_ids:
            _id(item)
        if len(set(self.media_ids)) != len(self.media_ids):
            raise RoomError('duplicate_media')


@dataclass(frozen=True)
class Listing:
    id: str
    owner: str
    content: ListingContent
    status: str
    visibility: str
    revision: int
    created_at: int
    updated_at: int
    expires_at: int

    def __post_init__(self):
        _id(self.id)
        if not isinstance(self.owner, str) or not self.owner.startswith('user:'):
            raise RoomError('invalid_principal')
        _id(self.owner[5:])
        if not isinstance(self.content, ListingContent):
            raise RoomError('invalid_content')
        if type(self.status) is not str or self.status not in STATUSES:
            raise RoomError('invalid_listing_status')
        if type(self.visibility) is not str or self.visibility not in {'private', 'public'}:
            raise RoomError('invalid_visibility')
        _integer(self.revision, 1, 2**63-1, 'invalid_revision')
        for value in (self.created_at, self.updated_at, self.expires_at):
            _integer(value, 0, 2**63-1, 'invalid_timestamp')
        if not self.created_at <= self.updated_at < self.expires_at:
            raise RoomError('invalid_listing_lifetime')
        if self.expires_at - self.created_at > MAX_LIFETIME_MS:
            raise RoomError('invalid_listing_lifetime')
        if self.status == 'draft' and self.visibility != 'private':
            raise RoomError('draft_must_be_private')


def _authorize(principal, scope):
    if not isinstance(principal, Principal):
        raise RoomError('authentication_required')
    _id(principal.user_id)
    if scope not in principal.scopes:
        raise RoomError('insufficient_scope')


def create_draft(principal, listing_id, content, now, lifetime_ms=30*86400000):
    _authorize(principal, 'listings:write')
    _integer(now, 0, 2**63-1, 'invalid_timestamp')
    _integer(lifetime_ms, 60000, MAX_LIFETIME_MS, 'invalid_listing_lifetime')
    return Listing(listing_id, principal.owner, content, 'draft', 'private', 1,
                   now, now, now + lifetime_ms)


def change_status(principal, listing, status, *, expected_revision, now, publish_consent=False):
    """CAS INTENT only: future storage must atomically compare and save revision."""
    _authorize(principal, 'listings:publish' if status == 'active' else 'listings:write')
    if listing.owner != principal.owner:
        raise RoomError('not_listing_owner')
    _integer(expected_revision, 1, 2**63-1, 'invalid_revision')
    if expected_revision != listing.revision:
        raise RoomError('revision_conflict')
    _integer(now, listing.updated_at, listing.expires_at-1, 'listing_expired_or_invalid_time')
    if type(status) is not str or status not in STATUSES:
        raise RoomError('invalid_listing_status')
    allowed = {'draft': {'active', 'archived'}, 'active': {'paused', 'fulfilled', 'archived'},
               'paused': {'active', 'fulfilled', 'archived'}, 'fulfilled': {'archived'},
               'archived': set(), 'blocked': set()}
    if status not in allowed[listing.status]:
        raise RoomError('invalid_listing_transition')
    if status == 'active' and publish_consent is not True:
        raise RoomError('publication_consent_required')
    return replace(listing, status=status,
                   visibility='public' if status == 'active' else listing.visibility,
                   revision=listing.revision+1, updated_at=now)


def public_projection(listing, now):
    """Allowlisted record, NOT HTML; render with maintained autoescaping templates.

    Media IDs are references, not proof of safe/public media. Their service must
    enforce publication and access. Callers cannot infer private listings exist.
    """
    _integer(now, 0, 2**63-1, 'invalid_timestamp')
    if listing.status != 'active' or listing.visibility != 'public' or now >= listing.expires_at:
        return None
    c = listing.content
    return {'id': listing.id, 'revision': listing.revision, 'title': c.title,
            'description': c.description, 'category': c.category, 'kind': c.kind,
            'modes': list(c.modes), 'locality': c.locality, 'region': c.region,
            'country': c.country, 'price_minor': c.price_minor, 'currency': c.currency,
            'media_ids': list(c.media_ids), 'created_at': listing.created_at,
            'updated_at': listing.updated_at, 'expires_at': listing.expires_at}
