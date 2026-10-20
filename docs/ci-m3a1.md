# M3a.1 CI evidence — opt-in user marketplace MCP and scoped delegation

Accepted source: [`405d2a34f7fe778c8cb80474aae6fba14cecf375`](https://github.com/LeonidYasin/mcp-rooms/commit/405d2a34f7fe778c8cb80474aae6fba14cecf375).
Later documentation/map updates are not a new runtime acceptance SHA. This is a
controlled composition API, not default CLI enablement or an updated VPS endpoint.

## Results

- [Push application CI](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39497669925), attempt1: success.
- [PR application CI](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39497679619): success.
- Python3.10/3.11/3.12/3.13 matrix, wheel/sdist and installed imports outside the source tree: green.
- Python3.12: **501 passed, 2 warnings**. Previous publication slice470;31 new auth/SDK/delegation cases.
- Python3.10: **452 passed, 30 skipped, 2 warnings**. Optional native decoding is still not accepted on3.10.
- [Documentation build/QA/deploy](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39497669888): success;15 diagrams, local links/assets, mobile overflow, search and screenshots.
- Aggregate at inspection:14 success,1 skipped,0 failed/pending. Includes docs/deploy; not14 application tests or merge permission.

An initial new test expected a `listings` key instead of the existing documented
`items` pagination key; the fixture assertion was corrected without changing the
API or dropping an ACL test. Final exact-SHA suite is green.
All project tests/package builds/SDK ASGI/browser checks ran in GitHub Actions.
Local work was file preparation, source reading and AST inspection only.

## Accepted behaviors

- Default issuer/app/CLI remain room-scope-only and register8 room methods. Listing
  credentials require explicit trusted scope policy; default app rejects such keys.
- Explicit same-store/resource bundle registers12 listing tools plus8 rooms through
  the official MCP SDK, with per-request Bearer authentication/ContextVar ownership.
  Actual secret authentication is exercised: no direct SQL seeding of listing scopes
  in the new SDK tests. Separate older core fixtures remain internal synthetic tests.
- Own create/get/list/categories/update; current revision/CAS; cross-user reads denied.
  Authenticated staged photo IDs attach through MCP. New-schema preview/consent/
  publish/withdraw/status workflow crosses the real SDK, with native upload still absent.
- Room keys gain no listing access. Listing read-only keys cannot mutate/confirm;
  listing-only keys gain no room rights. One-click signup remains rooms-only even
  in opt-in market app; no silent migration or self-requested scope escalation.
- Revoke/disable/expiry/resource/scope changes take effect on the next request;
  concurrent connections do not mix owners. Core operations still recheck persisted grants.
- Typed content rejects extra owner/media fields and bool/number coercion. Tool
  metadata has no actor/path/resource input. Narrow dispatcher denies forged actor
  fields, arbitrary actions, raw file paths and admin/process methods.
- Advisory ToolAnnotations mark reads and conservatively flag replacement/archive/
  publication/withdrawal. They do not grant permission or replace explicit consent.
- Stored publication status distinguishes current withdrawn epoch from a replayed
  historical active receipt. No external public-availability claim is derived from it.
- Self-service HTTP delegation rechecks persisted authority in the same issuance
  transaction; a revoke between gate auth and issuance cannot create a credential.
  Forged broader scope snapshots, stale/downgraded/foreign grants and malformed scope
  data fail closed. New scopes/expiry are bounded by the source; old key remains until
  explicit revoke. Raw secret is returned only by the no-store HTTP credential route.
- Wrong DB/resource bundle and missing namespace are refused without startup schema
  creation. Known storage failures are sanitized; secrets/paths are not logged/returned.

## Explicit operational changes and limits

`POST /credentials` now provides bounded delegation, **not renewal**: a copied key
cannot outlive its source expiry, including chains of copies. Clients get
expiry_bounded_by_source=true. Default7-day/max90-day trusted operator issuance is
unchanged. Account/session renewal, recovery and automatic marketplace onboarding
need separate reviewed flows; they are not silently replaced by manual registration.

This slice does not complete deployment milestone1: HTTP adapters, bounded native
streaming upload, browser sessions/CSRF, self-service marketplace grant policy and
connection/resource/abuse budgets remain. No new default service flag/CLI mode was
added. Root/file/worker lifecycle is owned by the trusted composition caller.
No listing-scoped real credentials, real publication, public search/photo endpoint,
private response/admin MCP, VPS/Caddy/main/release or production changed.

The existing owner-controlled Pages [single-publisher gate](ci-pages.md#remaining-single-publisher-configuration-gate)
remains. Docs deployment is not application deployment. See [user MCP contract](user-market-mcp.md)
and [six remaining deployment stages](deployment-readiness.md).
