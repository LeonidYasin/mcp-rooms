# M2c.2 CI evidence — publication transaction and withdrawal core

Accepted source: [`bc6d9d75bc591767b3aabfe72f2884772113fa67`](https://github.com/LeonidYasin/mcp-rooms/commit/bc6d9d75bc591767b3aabfe72f2884772113fa67).
The implementation is an internal opt-in core. No HTTP/MCP route, real listing,
credential issuance or VPS rollout is implied. Evidence/map changes are a later
documentation commit, not the runtime SHA below.

## Results

- [Push application CI](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39494105805), attempt1: success.
- [PR application CI](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39494113860): success.
- Python3.10/3.11/3.12/3.13, package builds and installed imports outside the tree: green.
- Python3.12: **470 passed, 2 warnings**. Previous accepted photo slice427;43 new publication cases.
- Python3.10: **421 passed, 30 skipped, 2 warnings**. Optional decoder skips are not native media acceptance on3.10.
- [Documentation build/QA/deploy](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39494105598): success;15 diagrams, local links/assets, mobile overflow, search, screenshots.
- Aggregate at inspection:14 success,1 skipped,0 failed/pending. Docs/deploy jobs included; not14 app tests or merge permission.

An earlier docs QA run rejected semicolon statement delimiters in a new Mermaid
sequence note. The note syntax was fixed; render checks were not removed/weakened.
All application tests/builds and browser/render checks ran in GitHub Actions only.
Local work was source/file preparation and static AST reading, not project execution.

## Accepted boundaries

- New-schema live-publication preview and explicit true consent, separately from
  both historical private intents. Exact allowlisted card preview is included;
  publication time is assigned later, not fabricated at preview time.
- Fresh owner/resource/scopes/revocation/category/revision/epoch/TTL/media checks
  before and after file I/O. Consent expiry does not extend draft/media lifetime.
- One write transaction consumes consent, saves snapshot and command receipt,
  and appends audit with actor/credential/command/intent ID and exact preview digest.
  Injected receipt/audit errors leave no partial publication or consumed consent.
- Dedicated publication epoch prevents reuse of a pending consent after withdrawal
  even if content did not change. Concurrent publication consumes once.
- Historical publish replay after withdrawal does not reopen; historical withdrawal
  replay after a later publication does not hide the new version.
- Legacy and photo-aware edit/archive/new-stage paths are frozen while active;
  withdraw first, then edit and obtain a fresh consent. Snapshot is not silently patched.
- Allowlisted public JSON and versioned photo primitives deny private/missing,
  withdrawn/disabled/expired/changed/corrupt content uniformly. Arbitrary blob paths
  and unselected photos are not public. Checks are repeated after file reads.
- Withdrawal can proceed when category/photo is broken; audit failure rolls it back.
  Credential revocation alone does not erase the user's publication; user disable hides it.
- Existing attached retention keeps photos through fixed draft/public expiry;
  reviewed cleanup can reclaim only after expiry+grace. No public pin bypass added.
- Explicit additive publication namespace, partial-namespace refusal and atomic DDL
  rollback; unchanged RoomStore identifiers and foreign-key integrity.

## Not acceptance of a public service

There is still no listing transport, streaming upload, browser session, frontend,
public search/feed, private response API or administrator MCP. Current enrollment
cannot issue listing scopes; tests use synthetic internal credentials only.
A consent boolean is not proof that a human reviewed the card. Before any real
publication an agent must obtain explicit owner approval of actual text/photos/terms.

Future adapters must implement autoescaped HTML, no-store/nosniff media delivery,
least-privilege auth, rate/size/concurrency controls and abuse/moderation policies.
No claim that downloaded copies can be revoked. Snapshot/consent/audit live in the
same private DB, with finite existing command/draft caps, not an infinite audit store.
Full DB+files disaster recovery, OS isolation and actual capacity remain gates.

No VPS, live schema/data/key, Caddy, main, release or production changed. Docs deploy
is not an application rollout. The owner-controlled Pages
[single-publisher gate](ci-pages.md#remaining-single-publisher-configuration-gate) remains.
See [publication design](live-publication.md) and [remaining deployment stages](deployment-readiness.md).
