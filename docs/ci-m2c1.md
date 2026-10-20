# M2c.1 CI evidence — versioned private photos and exact preview

Accepted source: [`0153bd98b5408e05b7abf8bcd5744d1ecbb08d57`](https://github.com/LeonidYasin/mcp-rooms/commit/0153bd98b5408e05b7abf8bcd5744d1ecbb08d57).
The implementation first passed at9adf5370; this accepted SHA additionally proves
legacy schema2 migration and transactional rollback after photo-link DDL.
Evidence/map updates are a later documentation commit, not the runtime SHA above.

## Results

- [Push application CI](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39490272942), attempt1: success.
- [PR application CI](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39490283338): success.
- Python3.10/3.11/3.12/3.13 matrix, wheel/sdist builds and installed imports outside the source tree: green.
- Python3.12: **427 passed, 2 warnings**. Previous accepted slice395;32 additional photo/migration cases.
- Python3.10: **378 passed, 30 skipped, 2 warnings**. Optional native codec/worker skips are not decoder acceptance on3.10.
- [Documentation build/QA/deploy](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39490272914): success;14 diagrams, local links/assets, mobile overflow, search and screenshots.
- Aggregate at inspection:14 success,1 skipped,0 failed/pending. Includes docs/deploy jobs; not14 application tests or merge authorization.

Tests, package builds and browser documentation checks ran only in GitHub Actions.
Local work was file preparation, source reading and static AST inspection; no local
project import/test/server/build/render and no remote VPS execution.

## Accepted behaviors

- Atomic owner-bound ordered0–8 photo IDs, canonical draft content + constrained
  links + manifest revision + command receipt. No hidden media IDs through text edits.
- CAS/replay, payload conflicts, capacity rollback, concurrent same-revision writers.
- Persisted owner/resource/scope/revocation checks before and after checksum I/O;
  checksums run outside SQLite write transactions under the cooperating root guard.
- Verified private preview binds text/category/version and ordered photo identity,
  digest/dimensions/size/policy/expiry. Reordering or editing invalidates prior intent.
- Legacy photo-unaware editor/preview cannot overwrite or silently omit attachments.
  Historical command replay is not a new mutation or a live publication approval.
- Attachment retention promotes only to the existing fixed draft deadline; detached
  media has a bounded grace. Cleanup does not delete attached media at the original
  staging deadline; expired/purged media cannot be revived.
- Eight maximum-size reservations fit the explicit16MiB candidate owner budget;
  global budget remains32MiB. This is a small bounded CI candidate, not a load claim.
- Corrupt selected bytes fail verification; owner may detach broken photos without
  serving them. Dual-manifest mismatch fails closed; no automatic repair/deletion.
- Explicit media1/2→3 migration preserves rows/bytes/RoomStore identifiers. Injected
  post-DDL failure rolls back links/version. Partial schema3 is refused, not recreated.
- Private intent expiry/replay and foreign-user reads remain denied as specified.
  Existing identity/room/draft/media/cleanup regressions remain in the full suite.

## Still not implemented or accepted

`private_photos_verified=true` is not a live publication gate. `media_ready=false`,
`publication_enabled=false` and `published=false` remain deliberate. There is no
human-review proof, live publisher, public card, upload transport, real listing-scope
issuance, private negotiations or administrator maintenance endpoint in this slice.

A live publisher requires a NEW notice/schema and fresh owner approval, atomic
revalidation/consume/state/audit and an explicit public projection. Do not upgrade
stored private intents into live consent. Full DB+files recovery, OS sandbox,
capacity/abuse acceptance and deployment approval remain separate gates.

No main merge, release, live schema/data/key, VPS service or Caddy configuration
changed. Docs deployment is not an application rollout. The existing
[single-publisher Pages configuration gate](ci-pages.md#remaining-single-publisher-configuration-gate)
remains owner-controlled. See [deployment estimate and gates](deployment-readiness.md).
