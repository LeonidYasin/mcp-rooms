# MCP Rooms roadmap

Current checkpoint: [M2c.1 CI](docs/ci-m2c1.md), versioned private photo drafts.
Next: live publisher, then the [7 milestones to useful external TEST](docs/deployment-readiness.md).
Older sections retain historical acceptance boundaries; they are not promises of a live service.

## Source extraction / private-pilot alpha

- [x] Owner approved public repository and MIT.
- [x] Copy focused room storage/maintenance/tests with immutable source provenance.
- [x] New local UUID users and per-connection random Bearer credentials; no GitHub prerequisite.
- [x] Digest-only storage, expiry/revocation/disable/resource/scopes, private-file CLI issuance.
- [x] Eight room tools over official MCP SDK; no other server tools/admin APIs.
- [x] New standalone SQLite application_id; explicit refusal of embedded DB identity.
- [x] Prepare core/recovery/auth/ASGI/admin tests and Python 3.10–3.13 CI/build workflow.
- [ ] Passing exact-HEAD CI and review of source/auth/dependency/licenses.
- [x] Separate operator-run loopback TEST accepted by supplied report; not public or boot-enabled.
- [x] Real external Notion static-header client and Qwen via local header-injection proxy.
- [x] Cross-user Qwen → room → Notion → room → Qwen round trip; final Qwen read operator-reported.
- [x] Agent verified own-message tombstone/readback and same-key retry returning the same message ID in a disposable room.
- [x] Cross-user live foreign-message delete / foreign-room close negatives; both directions, with readback unchanged.
- [x] Owner closes separate disposable rooms; original dialogue retained.
- [x] Controlled independent-user exchange and disposable revoke/replacement/disable/isolation negatives; no broad public-enrollment acceptance.
- [x] Prepare guarded snapshot → restore-to-new-path → Rooms-only restart helper and pure CI contracts.
- [x] Operator recovery drill: consistent snapshot, restore-to-new-path, integrity/counts/diagnostic messages and Rooms-only restart.
- [x] Authenticated Notion read and new send after restart.
- [x] Qwen reported reading the new post-restart reply and closing its own ACL canary; agent list confirms only original room remains.
- [x] Prepare disposable-user HTTP revocation/isolation and isolated-copy rewind/reconciliation drill; CI fixtures preserve an unrelated principal.
- [x] Operator-observed canary revocation/disabled-user rewind and reconciliation on an isolated restored copy; never overwrite/expose the live DB.
- [ ] General external revocation/change journal and reconciliation policy for real disaster recovery.
- [x] Operator live HTTPS disposable old-key revoke, same-user replacement/independent-user isolation, disabled-user rejection and complete canary cleanup.
- [x] Agent authenticated Notion read and fresh send after synthetic auth drill.
- [ ] Exact Qwen post-auth tool readback: reported ID matches but quoted text differs from actual send; not accepted as exact evidence, investigate in a future approved TEST.
- [ ] Disk/WAL/backups budgets, off-host recovery, alerting and measured capacity.
- [ ] Separately approved production release, deploy and rollback.

## Automatic signup and VPS preparation

- [x] One-click signup with empty JSON: no contact, questionnaire, GitHub or client UUID; not implicit tools/list signup.
- [x] One 256-bit server key shown once; stable user UUID separate from secret, digest-only storage.
- [x] Legacy pilot contact+UUID API compatibility; no required UI fields or contact-based recovery.
- [x] No automatic signup retries; new POST creates a new user, not recovery. Double-click guard and explicit lost-response warning.
- [x] Same-user scoped credential issuance and explicit current-key revoke via protected HTTP, not MCP tools.
- [x] Profiles/biographies optional room content only; want/offer exchange needs no personal data.
- [x] Persisted global signup caps and additive standalone v1->v2 migration, snapshot coverage.
- [x] Prepare read-only operator VPS preflight, isolated unit EXAMPLE and staged TEST plan.
- [x] Operator supplied clean read-only VPS preflight: Python 3.12.3, port 8765 free, no existing candidate user/path/unit; not installation authorization.
- [x] Prepare checksum-pinnable new-service installer, conservative data-preserving rollback and pure/mocked/ASGI acceptance coverage.
- [x] Operator-reported isolated loopback install accepted at runtime SHA 4b2351c0b6522d30c888496b3c1774be8791345f; two users, rotation, SQLite integrity; protected services unchanged.
- [x] Prepare root-only read-only Caddy inspector with private snapshot and secret-sanitized routing report.
- [x] Fresh operator proxy report: one host server, no prefix collision, ETag available; rooms active.
- [x] Prepare explicit 30-minute public-signup TEST route with scoped CAS insert/delete, persistent cleanup/manual fallback and no old auth bypass.
- [x] Operator HTTPS-route report: local TLS gate passed; timer armed, external client gate still pending.
- [x] Fix public-signup top-level cross-site navigation regression in source; API/foreign-Origin/iframe protection retained.
- [x] Real external-client/two-chat exchange with distinct pseudonymous owners.
- [x] Operator accepted 24-hour HTTPS TEST window with signup disabled, existing keys preserved, protected services unchanged.
- [x] Operator-observed manual cleanup: own route removed, Rooms stopped/PID0, override removed, original 2h limit and DB preserved.
- [ ] Calendar-triggered automatic 24-hour cleanup remains untested: window was closed manually early.
- [ ] Reviewed runtime update for navigation fix; installed runtime remains 4b2351c0.
- [ ] Proxy access/anti-abuse policy, separately approved temporary route and live signup/client gates.
- [ ] Ownership-verified recovery/moderation/Sybil control before broad public onboarding.

## Shared core / compatibility

- [ ] Differential embedded/standalone contract fixtures (document intentional identity differences).
- [ ] Canonical versioned core + pinned embedded GitHub compatibility adapter.
- [ ] Separate reviewed identity/data migration; no automatic conversion of existing VPS DB.
- [ ] Agora integration after contract acceptance; market/embedding matching separate from storage.

## Broader onboarding

- [ ] Maintained OAuth 2.1 authorization-server adapter, discovery/PKCE/audience and real client gates.
- [ ] Proven account linking by issuer/subject, recovery/abuse review, independent agent delegation.
- [ ] Private rooms/moderation/public-market security only after an explicit product decision.

No automatic deployment, autonomous agents, endless history, E2EE, A2A, matching or payments claimed.


## Desktop client assets (saved, no runtime deploy)

- [x] Save delivered Qwen header adapter and read-only handshake/check in clients/qwen.
- [x] Add setup/debug/offline/security instructions, dependencies, placeholder-only .env and key-free Qwen JSON.
- [x] Add Linux mocked-upstream CI contracts for header injection, secret-free tracing, bounds, redirects/errors/SSE cleanup.
- [ ] Future Qwen native-header/final raw-tool exact-read regression acceptance if another TEST is approved.

## Web market / separate admin — owner-directed next phase

Detailed [mindmap](docs/product-mindmap.md), [relationships](docs/architecture-graph.md),
[admin boundary](docs/admin-mcp-design.md), [first-sale gates](docs/first-sale-acceptance.md).
Open to all locations; no one-town registration restriction. C2C goods/services first,
structured rides/delivery later. Supersedes the previous B2B-only niche suggestion.

- [x] Save detailed mindmap, component/trust/data graphs and operator/admin boundaries.
- [x] Start pure listing field/status/publication-consent/public-projection contracts,
  with CI test sources. Not a persistent API or completed atomic CAS implementation.
- [x] Prepare responsive standalone demo listing, catalogue, empty/modal states;
  honest missing-photo state, no fake seller/rating/click success. Not a live web app.
- [ ] Exact-HEAD CI/review for this new slice (previous baseline 152 tests passed).
- [ ] Additive categories/listings/media SQLite migration + backup/restore on copy.
- [ ] Transactional listing service: owner/scopes/CAS/idempotency/caps and expiry.
- [ ] Real photo upload/re-encoding/EXIF stripping/ownership/publication/media budgets.
- [ ] Web form/preview/public URL + server-rendered safe output and revocable sessions.
- [ ] User listings MCP draft/publish/search/update/close, shared records with web.
- [ ] Separate admin MCP app/auth/read-only tools; negative audience/scope tests.
- [ ] Admin moderation/categories/audit/confirmation and manual operator boundary.
- [ ] Private response/negotiation ACL: current shared rooms are not private.
- [ ] Approved isolated TEST and first real-item publication/find/respond trial.
- [ ] Authorized web room viewer with same membership and bounded active-window reads.
- [ ] Communities/categories/subscriptions; useful filters without bot-vote ranking.
- [ ] Quote/order/atomic single assignment for rides/delivery, privacy/legal review.
- [ ] Optional provider-independent matching/embeddings; no mandatory paid LLM.
- [ ] Commercial tiers only after actual useful replies and repeated use, not fabricated demand.

Merge, release and production deployment remain separate approvals. Existing VPS
services/data/main are unchanged; the closed TEST is not reopened by code publication.

## Marketplace reuse research gate

- [x] GitHub + official web research across classifieds, community, commerce, agent rooms, MCP/A2A and transport; [final evidence and shortlist](docs/marketplace-research-final.md).
- [x] Record actual first item: used toilet, removed and washed; no claims about disinfection, condition, price or publication.
- [ ] Bounded HivePress/ListingHive/official WordPress MCP Adapter evaluation: free features, no-email identity, per-actor write rights, separate admin MCP, media/privacy and rollback.
- [ ] If blocked, evaluate Apache OsclassPoint; no parallel installation of every engine.
- [ ] Owner-approved ADR selecting reuse vs minimal existing Python/SQLite implementation before persistent listing/account/moderation work.

Desk research is complete enough for selection, not runtime/security acceptance. No new
market features, main merge or VPS change is implied. Existing Rooms pilot remains separate.

## Equal build-vs-reuse architecture gate

- [x] Static review of HivePress user/listing paths, Osclass registration and WordPress MCP permissions documentation; [results and own-code debts](docs/candidate-source-checks.md).
- [x] Include minimal Python/SQLite domain as an equal candidate, not an automatically inferior fallback.
- [ ] Define shared backend-independent conformance contract and negative cases.
- [ ] Verify bounded finalist slices in approved CI/test environment; no vendor-core edits, shared-admin shortcut or duplicate writable catalog.
- [ ] Select architecture by verified integration + maintenance cost; no invented timing/scores or automatic preference for reuse/custom.

## Concrete outcome after candidate review

- [x] Select bounded own Python/SQLite modular domain as the next MVP direction; [ADR-001](docs/decisions/001-marketplace-foundation.md). No WordPress/Osclass install or second identity store.
- [x] Specify common backend-independent [conformance cases](docs/marketplace-conformance.md); NOT an implemented or passed integration suite.
- [ ] Slice 1: persistent category/draft + atomic CAS/idempotency + unchanged room compatibility.
- [ ] Slice 2: validated photos, preview/content-bound consent, public card/search/unpublish.
- [ ] Slice 3: same application commands via safe browser sessions and scoped listing MCP.
- [ ] Slice 4: private response and isolated minimal admin MCP/moderation/audit.
- [ ] Slice 5: CI acceptance/recovery/capacity, separately approved operator TEST, real-item/independent-response evidence.

The historical candidate-evaluation checklist above is superseded by ADR-001 for work
ordering; runtime comparison/deployment claims remain unproven. Reopen alternative
evaluation only for a documented blocker or a concrete better maintenance trade-off.

## M1a source slice — no public integration

- [x] Canonical [delivery plan](docs/delivery-plan.md): dependency graph, milestones, risk gates and evidence vocabulary.
- [x] Shared domain primitives; backward-compatible RoomError/Principal aliases.
- [x] Prepare explicit additive market namespace and small category hierarchy without room user_version/default startup changes.
- [x] Prepare private draft persistence/reopen/owner access, persisted credential+resource+scope rechecks, atomic revision and command receipts.
- [x] Prepare bounded lifetime caps and negative/concurrency/rollback/regression CI fixtures.
- [x] Exact-code-SHA CI acceptance of M1a at `784b4c6b`: 8/8 checks, Python3.10–3.13; Python3.12 log 197 passed/2 warnings. [Evidence](docs/ci-m1a.md). This is not full marketplace conformance.
- [ ] Full M1b lifecycle/read-list/category API/retention and command contracts.

No signup scope expansion, registered listing tools/routes, media, publish, private response,
admin MCP or live migration is implied. [Storage design](docs/draft-storage-design.md).

## M1b.1 — private navigation/lifecycle, no public integration

- [x] Prepare bounded owner-scoped list with actor/status-bound keyset cursor and no foreign totals.
- [x] Prepare category immediate-child reads with active ancestry and explicit capacity bound.
- [x] Prepare terminal private archive, version CAS/receipt atomicity, rollback and archive/update race tests.
- [x] Prepare explicit market namespace v1→v2 migration preserving old rows/receipts; room version/startup unchanged.
- [x] Exact-code-SHA CI of M1b.1 at `104d5a5c`: 8/8 checks, Python3.12 226 passed/2 warnings, full existing regression. [Evidence](docs/ci-m1b1.md).
- [ ] Remaining M1b: content-bound consent + publication policy and retention/delete/retry horizon; quota reserve for protective actions before public access.

[Lifecycle/migration contract](docs/private-draft-lifecycle.md). Archiving is not physical
erasure, publication or proof of sale. No VPS change or listing scopes issued by signup.

## M1b.2 source — exact private preview / bounded intent

- [x] Prepare deterministic preview of exact record/category path/resource/policy notice; untrusted text is not HTML.
- [x] Prepare separate listings:publish permission checks, short-lived private intent, replay without deadline extension and fresh validity read.
- [x] Prepare negative/revoke/expiry/revision/category/resource/rollback/concurrency fixtures; no publication or scope issuance.
- [x] Exact-code-SHA CI of M1b.2 at `2108b93e`: 8/8 checks, Python3.12 247 passed/2 warnings. [Evidence](docs/ci-m1b2.md).
- [ ] Actual publisher: new live-publication notice/media manifest, transactional recheck+one-time consume+state transition/audit, approved public API.

[Intent contract](docs/publication-intent.md). [Positioning](docs/project-positioning.md):
technical test item is not the public brand hero. GitHub About update attempted but
blocked by token HTTP403; README/package description updated in the working branch.


## Vision / M2a — bounded photo preparation

- [x] Broaden documented vision to opportunities from personal AI chats, without claiming shipped jobs/investment verticals.
- [x] Prepare optional bounded JPEG/PNG normalizer and synthetic negative fixtures; no upload/paths/network/publication.
- [x] Exact-SHA M2a CI at `110393e9`: 8/8 checks; Python3.12 267 passed/2 warnings; Python3.10 core247 passed/1 optional-media module skipped/2 warnings. [Evidence](docs/ci-m2a.md).
- [ ] OS-limited decode worker; authenticated media ownership, storage/quotas/retention and served derivative contract.
- [ ] Actual listing publish/consent transaction, public web/user MCP, private response and separate admin gate.

[Opportunity boundaries](docs/opportunity-model.md), [photo safety contract](docs/media-image-safety.md).
About is proposed text for the owner's manual update, not an API metadata mutation.


## Documentation website / living project map

- [x] Prepare MkDocs/Material site with source-linked component registry, mindmap, architecture, roadmap and contracts.
- [x] Exact source SHA and history on every page; version manifest and Markdown content digests.
- [x] Prepare build/QA/artifact/deploy workflow; PR never deploys; source remains alpha branch.
- [x] Exact-SHA docs build +11 rendered diagrams/link/mobile/search smoke and visual review at `6fd4f7ad`. [Evidence](docs/ci-pages.md).
- [x] Pages deploy succeeded at `6fd4f7ad`; external version manifest matched SHA/development channel. Initial environment rejection resolved without an agent settings change or bypass.

Documentation publication is not application rollout or approval to merge main.

- [ ] Single-publisher gate: owner selects Pages Source **GitHub Actions**, removing the competing branch/Jekyll build; next push + external source SHA verified. Custom deploy already passed; reliability is not inferred from one successful response. [Evidence](docs/ci-pages.md#remaining-single-publisher-configuration-gate).


## M2b.1 — internal decode worker

- [x] Prepare stdlib supervisor, one-shot child rlimits, bounded pipes/deadline and immediate admission.
- [x] Prepare synthetic codec and failure fixtures; no local project execution.
- [x] Exact-SHA CI at `583df1b9`: Python3.12 294 passed/2 warnings; Python3.10 core247 passed/28 skips/2 warnings. [Evidence](docs/ci-m2b1.md).
- [ ] Prove dedicated OS filesystem/network sandbox on operator-approved TEST.
- [ ] Implement private staged derivatives, owner checks, durable manifests and reconciliation.

[Worker boundary](docs/media-worker.md). No VPS, main, public upload or listing publication changed.


## M2b.2 — private derivative filesystem primitives

- [x] Prepare fixed-root dirfd layer, exclusive files, durable writes and digest reads.
- [x] Prepare bounded inventory quotas, symlink/hardlink/FIFO, corruption, I/O and concurrency fixtures.
- [x] Exact-SHA CI at `4eebfce4`: Python3.12 330 passed/2 warnings; application matrix and docs QA green. [Evidence](docs/ci-m2b2.md).
- [x] Add persisted owner-authorized media reservations/manifests in M2b.3; no raw-key read API. [Evidence](docs/ci-m2b3.md).
- [ ] Add reconciliation/retention and consistent DB+files recovery.

[Boundary](docs/media-private-files.md). No public upload, attachment or publication yet.


## M2b.3 — owner-authorized private staging

- [x] Prepare opt-in SQLite staging, fixed-budget reservations, resource/draft/owner checks and safe replay.
- [x] Prepare revoke/change-during-decode, read recheck, quota/retry/concurrency and pipeline fixtures.
- [x] Exact-SHA CI at `d2a405a8`: Python3.12 368 passed/2 warnings; Python3.10 319 passed/30 skipped/2 warnings; application matrix + docs QA green. [Evidence](docs/ci-m2b3.md).
- [x] Versioned photo attachment and ordered private preview/intent checked in M2c.1; live publication consent remains a separate gate.
- [ ] Reviewable reconciliation/retention and safe budget reclamation/recovery.

[Staging boundary](docs/media-staging.md): no public API, attach, scope issuance or VPS migration.


## M2b.4 — reviewed retention and quota reclamation

- [x] Prepare bounded read-only plan and exact snapshot/store binding.
- [x] Prepare PURGING/PURGED, durable absence before quota release, retained bounded receipts.
- [x] Coordinate stage writes with cleanup, including late worker and interrupted cleanup fixtures.
- [x] Exact-SHA CI at `f5a7aada`: Python3.12 395 passed/2 warnings; Python3.10 346 passed/30 skipped/2 warnings; application matrix +13-diagram docs QA green. [Evidence](docs/ci-m2b4.md).
- [ ] Explicit orphan recovery, complete DB+files restore and receipt compaction policy.
- [ ] Operator/admin authorization, scheduling and approved OS TEST; no automatic cleanup enabled.

[Cleanup boundary](docs/media-cleanup.md). No VPS, main, live schema migration or public maintenance API.


## M2c.1 — versioned photo attachment / private intent

- [x] Prepare media schema3, atomic ordered photo links/content/revision/receipt.
- [x] Prepare photo-aware text edits, verified preview/private intent v2, legacy bypass refusal.
- [x] Prepare retention promotion/detach, eight-photo budget and revoke/race/intent fixtures.
- [x] Exact-SHA CI at `0153bd98`: Python3.12 427 passed/2 warnings; Python3.10 378 passed/30 skipped/2 warnings; matrix +14-diagram docs QA green. [Evidence](docs/ci-m2c1.md).
- [ ] Live publisher needs a new notice/consent contract, atomic consume/state/audit and public projection.

[Photo boundary](docs/photo-drafts.md); [remaining deployment milestones](docs/deployment-readiness.md).
No main, VPS, public upload/publication or new real scope issuance changed.
