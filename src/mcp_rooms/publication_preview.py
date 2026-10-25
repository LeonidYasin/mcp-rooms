"""Live consent is a NEW contract; private intents never become public approval."""
from hashlib import sha256
from .preview_contract import canonical_json

PUBLICATION_SCHEMA = 'mcp-rooms/live-publication-consent/v3'
NOTICE = ('A separate publish command will expose this exact card and photos to anyone '
          'through explicitly enabled public adapters. Review all text, price, location '
          'and photos: personal details written there will be public. Private rooms, '
          'credentials and account details are not included. Withdrawal stops future '
          'service reads, but cannot erase copies already obtained by others. '
          'Agent delegation is not proof of human review. Public transport availability depends on the server composition; this preview does not enable it.')


def public_card(record, category_path, photos, epoch, now, *, author):
    """build an author-signed public card. `author` is the display name only, never
    the raw user UUID, credential or any contact; adapters must escape it."""
    listing = record['listing']
    content = listing['content']
    card = {name: content[name] for name in ('title','description','category','kind','modes',
            'locality','region','country','price_minor','currency')}
    card.update(id=listing['id'], revision=listing['revision'], publication_revision=epoch,
                category_id=record['category_id'], category_path=category_path,
                photos=photos, published_at=now, expires_at=listing['expires_at'],
                author=author)
    return card


def publication_preview(record, category_path, resource, photos, epoch, *, author):
    document = dict(schema=PUBLICATION_SCHEMA, resource=resource, notice=NOTICE,
                    record=record, category_path=category_path, photos=photos,
                    publication_epoch=epoch, audience='public_web_and_agents',
                    card_preview=public_card(record,category_path,photos,epoch+1,None,author=author),
                    publication_transaction_available=True, public_transport_enabled=None)
    digest = sha256((PUBLICATION_SCHEMA+'\0'+canonical_json(document)).encode()).hexdigest()
    return {**document, 'digest': digest}
