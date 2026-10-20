# M3b.2 CI evidence — opt-in same-origin browser session HTTP bridge

Accepted application source:
[`e91d5b195d3399911dd331034f1941d488a23220`](https://github.com/LeonidYasin/mcp-rooms/commit/e91d5b195d3399911dd331034f1941d488a23220).
A later documentation checkpoint is not a different accepted runtime SHA.
This accepts only a bridge for existing credentials, not marketplace onboarding,
a browser listing form or cookie authority over market/media commands.

## Verification

- [Push application CI, attempt1](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39506292058): success, Python3.10–3.13, wheel/sdist and installed-package checks.
- [PR application CI](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39506301540): success for the same SHA.
- Python3.12: **623 passed, 2 warnings**;43 additional parametrized HTTP cases over M3b.1.
- Python3.10: **573 passed, 31 skipped, 2 warnings**; optional native decoder remains >=3.11.
- [Documentation build/QA/deploy](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39506292022):15 diagrams, local links/assets, mobile overflow, Cyrillic search and screenshots passed.
- Aggregate at inspection:14 successful checks,1 skipped,0 failures/pending. This includes docs/deploy and does not authorize merge or VPS deployment.
- Repository-native AI handoff integrity checks ran in the application matrix.

The initial insecure-transport test tried to start the same official SDK app
lifespan twice. The SDK rejected this. The fixture now constructs an independent app
for that probe; HTTPS/header-spoofing assertions were retained. No runtime policy or
negative test was weakened to make CI green.

All tests, package builds and site/browser rendering ran only in Actions. Local
preparation used text editing/AST inspection, no application execution. Credentials,
DBs and cookies were synthetic; no real login, VPS request or publication occurred.

## Accepted transport boundary

Explicit same-bundle/schema-checked composition, default404 without browser sessions.
POST existing Bearer → separate short session, default read-only and no scope elevation;
GET safe context/CSRF; DELETE session-only logout with CSRF. __Host cookie has Secure,
HttpOnly, SameSite=Strict, Path=/, no Domain, Max-Age bounded by server deadline.
No session/MCP secret in JSON, no persistent frontend Bearer or URL secret.

Exact HTTPS ASGI scheme/Host/Origin; a GET without Origin requires exact same-origin
Fetch Metadata. No cross-site/same-site/navigation allowance or CORS. Forwarded headers
do not make an insecure request HTTPS. No silent cookie/account replacement. Duplicate
cookies/JSON/headers and unknown actor/TTL fields are rejected. Auth precedes body;
1024-byte incremental bound,10s timeout, length/encoding/disconnect checks, fresh parent
authority at session creation. Bounded per-process admission/login windows are tested,
not certified fleet anti-bot/load protection. Network send failure releases admission
without issuing a second response.

Parent revoke/disable and idle expiry invalidate bootstrap and clear the browser
cookie; parent key survives logout. Browser cookie/bs1 token does not authenticate
MCP, identity, admin or agent upload routes. HTTPX/ASGI cookie checks are not a native
browser SameSite/security-policy acceptance; that remains required before web launch.

## Deliberate integration stop / next gate

**M3b.3 transaction-time session authority:** the current listing/media Principal
checks the parent credential. It cannot yet prove the browser session itself remains
valid while a slow upload/worker runs. Consequently no market/media operation accepts
this cookie. Add trusted backward-compatible session binding and authorization in
the same core SQLite transaction, with revoke/logout/expiry-during-I/O negatives,
BEFORE wiring typed browser listing commands or the photo form.

Also remaining: automatic contact-independent onboarding/grant policy, renewal/lost-key
recovery, session retention before lifetime caps become UX, real browser QA, public
projection/search, independent private response/admin MCP, trusted edge/TLS transport,
OS/load/DoS budget and DB+files/security-state recovery. Default CLI is unchanged;
no main merge, release, VPS/Caddy/real credential/database change. Pages remains a
docs site with its [owner-controlled single-publisher gate](ci-pages.md#remaining-single-publisher-configuration-gate).
See [contract](browser-http.md), [handoff](ai-handoff.md), [work-state](work-state.json)
and [six major stages to useful external TEST](deployment-readiness.md).
