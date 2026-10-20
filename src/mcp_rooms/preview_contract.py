"""Canonical private preview data, not HTML, a signature or a public projection."""
import hashlib
import json

PREVIEW_SCHEMA = 'mcp-rooms/private-publication-intent/v1'
NOTICE = ('Publication is not enabled. Confirmation records a short-lived private '
          'intent for this exact version only; it does not publish or prove human review.')


def canonical_json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def make_preview(record, category_path, resource):
    """Trusted service data only; caller validates ownership, state and taxonomy.

    Text remains untrusted data. Future HTML must escape it. Changing the future
    publication notice/media manifest requires a new schema and a fresh approval.
    """
    document = {'schema': PREVIEW_SCHEMA, 'resource': resource, 'record': record,
                'category_path': category_path, 'notice': NOTICE,
                'media_ready': False, 'publication_enabled': False}
    digest = hashlib.sha256((PREVIEW_SCHEMA + '\0' + canonical_json(document)).encode('utf-8')).hexdigest()
    return {**document, 'digest': digest}
