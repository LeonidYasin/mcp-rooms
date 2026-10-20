# M2b.4 CI evidence — reviewed retention and quota reclamation

Accepted source: [`f5a7aada1eb2fe55149bd3f3efbee207581cbd9a`](https://github.com/LeonidYasin/mcp-rooms/commit/f5a7aada1eb2fe55149bd3f3efbee207581cbd9a).
Evidence and map statuses are a later docs-only commit; this is the exact runtime
SHA checked below, not a claim that later behavior changes were tested.

## Results

- [Push application CI](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39487421567), attempt1: success.
- [PR application CI](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39487427139): success.
- Python3.10/3.11/3.12/3.13 matrix, wheel/sdist build and installed imports outside source: green.
- Python3.12: **395 passed, 2 warnings**; previous staging slice368,27 cleanup cases added.
- Python3.10: **346 passed, 30 skipped, 2 warnings**. Optional codec/worker skips are not media decoding acceptance on3.10.
- [Documentation build/QA/deploy](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39487421654): success.13 diagrams, local links/assets, mobile overflow, search and screenshots.
- Aggregate at inspection:14 success,1 skipped,0 failed/pending. Includes docs/deploy jobs; not14 app tests or permission to merge.

All runtime/build/browser work ran in GitHub Actions. Locally only source preparation,
static AST/registry inspection and reading code were performed. No local project execution.

## Accepted behaviors

- Read-only, redacted dry run; fresh reviewed plan application, strict plan shape,
  digest/store identity, TTL and recheck after checksumming.
- Expired+grace retention, durable file absence before byte/active-row quota release.
  Old command receipts remain tombstones and cannot recreate uploads after purge.
- Separate lifetime tombstone cap; byte quota can be reused by a new UUID without
  resetting receipt history or silently promising infinite operations.
- Changed rows, changed file metadata or a new reservation during apply invalidate
  the reviewed snapshot before deletion.
- Orphan/unknown/symlink/hardlink/corrupt files and missing active derivatives block
  destructive apply. Missing expired data may retire after durable absence.
- Unlink/fsync/final-DB failures and partially completed batches preserve recoverable
  PURGING state; a fresh reviewed plan resumes safely without premature quota release.
- Expired in-flight worker cannot write after reclamation. Cleanup waits for a
  cooperating writer's file+manifest boundary rather than racing its uncommitted bytes.
- Failed decode without a file is reclaimable after grace; reappeared purged files
  are reported and not automatically deleted.
- Explicit additive media schema1→2 migration preserves data/files. Injected migration
  failure rolls back columns/version atomically. Rooms schema identifiers unchanged.
- Existing worker/file/staging and room/identity/draft regressions remain in the full suite.
  Staging now rechecks rights before file creation as well as before final commit.

## Explicit limits

Internal operator code only: no user-facing cleanup endpoint, admin MCP credential,
CLI command, timer or automatic request-triggered cleanup has been added. A plan
digest is not authorization. Dedicated admin authentication/audience/scopes/audit
must exist before any maintenance exposure.

Orphans are blockers, not an automatic deletion/adoption stream. No arbitrary-path
delete exists. Full DB+files restore/revocation reconciliation, explicit orphan
recovery, receipt compaction and load/OS sandbox acceptance remain separate gates.
Cleanup-resume fixtures are not a complete disaster-recovery proof. No strong
protection against hostile same-UID or privileged filesystem mutation is claimed.

No VPS, real schema/data/credential, service/Caddy, main, release or public application
changed. Documentation deployment is not an application rollout. The prior Pages
[single-publisher configuration gate](ci-pages.md#remaining-single-publisher-configuration-gate)
remains owner-controlled and is not inferred complete from green deploy checks.
