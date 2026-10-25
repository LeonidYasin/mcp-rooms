"""Explicit trusted marketplace bundle and narrow user-command adapter.

No root/SQL/admin/media decode paths or migrations exposed to clients. Authentication
is performed by BearerGate; persisted grants are rechecked in every core operation.
"""
import logging
from pathlib import Path
import sqlite3
from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr, ValidationError
from .domain import DomainError, Principal
from .listing_contract import ListingContent
from .publication_guard import publication_schema

LOG = logging.getLogger(__name__)


class ListingInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    title: StrictStr
    description: StrictStr
    category: StrictStr
    kind: StrictStr
    modes: list[StrictStr]
    locality: StrictStr = ''
    region: StrictStr = ''
    country: StrictStr = ''
    price_minor: StrictInt | None = None
    currency: StrictStr | None = None

    def domain(self):
        values = self.model_dump()
        values['modes'] = tuple(values['modes'])
        return ListingContent(**values)


READ = frozenset({'get','list_own','categories','preview','publication_status','public_get','public_index'})
PUBLISH = frozenset({'confirm','publish','withdraw'})
ARGUMENTS = {
    'create': {'content','category_id','client_id'},
    'get': {'listing_id'},
    'list_own': {'status','cursor','limit'},
    'categories': {'parent_id'},
    'update': {'listing_id','content','category_id','expected_revision','client_id'},
    'set_photos': {'listing_id','media_ids','expected_revision','client_id'},
    'archive': {'listing_id','expected_revision','client_id'},
    'preview': {'listing_id'},
    'confirm': {'listing_id','expected_revision','preview_digest','consent','client_id'},
    'publish': {'listing_id','intent_id','client_id'},
    'withdraw': {'listing_id','expected_publication_revision','client_id'},
    'publication_status': {'listing_id'},
    'public_get': {'listing_id'},
    'public_index': {'section','limit'},
}


class MarketAdapter:
    def __init__(self, drafts, photos, publisher):
        if (photos.drafts is not drafts or publisher.photos is not photos
                or publisher.drafts is not drafts or publisher.store is not drafts.store):
            raise DomainError('market_binding_mismatch')
        self.drafts, self.photos, self.publisher = drafts, photos, publisher
        self.store, self.resource = drafts.store, drafts.resource

    def check_binding(self, database, resource):
        if Path(database) != self.store.path or resource != self.resource:
            raise DomainError('market_binding_mismatch')
        with self.store._db() as db:
            self.drafts._schema(db)
            self.photos.stages._schema(db)
            publication_schema(db)
        # Only schema reads here. Startup never initializes marketplace tables.

    def _status(self, actor, listing_id):
        with self.store._db() as db:
            self.drafts._schema(db); publication_schema(db)
            now = self.store.clock()
            self.drafts._authorize(db,actor,'listings:read',now)
            self.drafts._owned(db,actor.user_id,listing_id,now)
            row = db.execute('SELECT state,epoch,revision,updated_at,expires_at FROM listing_publications WHERE listing_id=? AND user_id=?',
                             (listing_id,actor.user_id)).fetchone()
            if not row:
                return {'publication':{'state':'never_published','publication_revision':0}}
            if now < row['updated_at']:
                raise DomainError('invalid_timestamp')
            return {'publication':{'state':row['state'],'publication_revision':row['epoch'],
                    'source_revision':row['revision'],'updated_at':row['updated_at'],
                    'expires_at':row['expires_at'],'expired':now>=row['expires_at']}}

    def execute(self, actor, action, **args):
        try:
            if not isinstance(actor,Principal):
                raise DomainError('authentication_required')
            if action not in ARGUMENTS:
                raise DomainError('method_unavailable')
            if not args.keys() <= ARGUMENTS[action]:
                raise DomainError('invalid_arguments')
            scope = 'listings:read' if action in READ else 'listings:publish' if action in PUBLISH else 'listings:write'
            # Also protects direct adapter calls; never trust only a scope snapshot.
            with self.store._db() as db:
                self.drafts._authorize(db,actor,scope,self.store.clock())
            if 'content' in args:
                value=args['content']
                args['content']=(value if isinstance(value,ListingInput) else ListingInput.model_validate(value)).domain()
            if 'media_ids' in args:
                if type(args['media_ids']) is not list:
                    raise DomainError('invalid_media')
                args['media_ids']=tuple(args['media_ids'])
            methods = {'create':self.drafts.create,'get':self.drafts.get,'list_own':self.drafts.list_own,
                'categories':self.drafts.categories,'update':self.photos.update_content,
                'set_photos':self.photos.set_photos,'archive':self.drafts.archive,
                'preview':self.publisher.preview,'confirm':self.publisher.confirm,
                'publish':self.publisher.publish,'withdraw':self.publisher.withdraw,'publication_status':self._status,
                'public_get':lambda _a,**k:self.publisher.public_get(**k),
                'public_index':lambda _a,**k:self.publisher.public_index(**k)}
            return {'ok':True,**methods[action](actor,**args)}
        except DomainError as exc:
            return {'ok':False,'error':exc.code,**exc.details}
        except (ValidationError,TypeError,ValueError):
            return {'ok':False,'error':'invalid_arguments'}
        except sqlite3.Error as exc:
            code=getattr(exc,'sqlite_errorcode',0)
            code=(code & 255) if type(code) is int else 0
            LOG.warning('market_storage_failure sqlite_primary_code=%d',code)
            if code in (5,6):return {'ok':False,'error':'market_storage_busy','retryable':True,'retry_after_ms':250}
            return {'ok':False,'error':'market_storage_unavailable'}
        except OSError:
            return {'ok':False,'error':'market_storage_unavailable'}
        except Exception:
            return {'ok':False,'error':'market_request_failed'}
