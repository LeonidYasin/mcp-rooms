"""Private, photo-aware preview. NOT a live-publication approval contract."""
from hashlib import sha256
from .preview_contract import canonical_json

PHOTO_PREVIEW_SCHEMA = 'mcp-rooms/private-photo-intent/v2'
PHOTO_NOTICE = ('Publication is not enabled. This private intent binds the exact text, '
                'photo order and checked derivatives; it neither publishes nor proves '
                'that a human reviewed the content. A live publisher requires a new contract.')


def make_photo_preview(record, category_path, resource, photos):
    document = dict(schema=PHOTO_PREVIEW_SCHEMA, resource=resource, record=record,
                    category_path=category_path, notice=PHOTO_NOTICE, photos=photos,
                    private_photos_verified=True, media_ready=False, publication_enabled=False)
    digest = sha256((PHOTO_PREVIEW_SCHEMA+'\0'+canonical_json(document)).encode()).hexdigest()
    return {**document, 'digest': digest}
