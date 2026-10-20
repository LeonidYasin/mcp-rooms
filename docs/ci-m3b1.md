# M3b.1 — CI evidence: browser session core + repository-native AI handoff

Accepted application source:
[`ce8f1ea1d90628e98c9b0421ebaad243039db977`](https://github.com/LeonidYasin/mcp-rooms/commit/ce8f1ea1d90628e98c9b0421ebaad243039db977).
Later docs/checkpoint commits do not replace this runtime acceptance SHA.
No HTTP cookie login, browser form or public endpoint is enabled by this slice.

## Exact-SHA verification

- [Push application CI, attempt1](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39504026512): Python3.10–3.13, wheel/sdist and installed package checks succeeded.
- [PR application CI](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39504033792): same source matrix succeeded.
- Python3.12: **580 passed, 2 warnings**, up41 from M3a.2:34 session-core cases +7 handoff integrity cases.
- Python3.10: **530 passed, 31 skipped, 2 warnings**. Native decoder remains optional >=3.11; session core and handoff checks run on3.10.
- [Documentation build/QA](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39504026402):15 diagrams, local links/assets, mobile overflow, Cyrillic search and screenshots succeeded.
- New `Validate AI continuation handoff` step succeeded; source run correctly recorded the then-accepted M3a.2 SHA and M3b.1 SOURCE, before this acceptance update.

An initial docs commit placed the handoff menu item inside MkDocs validation.nav
rather than root nav. Strict documentation build caught the configuration error.
Only placement was corrected; no validation was removed or weakened. Application
matrix already passed; all final checks must still refer to the accepted SHA above.

Project tests/builds/child workers and site render/browser QA ran only in Actions.
Local work was text preparation and AST parsing, without importing/executing project
code. Only synthetic users/keys/databases, no real login or VPS operation.

## Accepted session boundary

Explicit browser schema1; separate digest-only bs1 namespace; listing-only subset
of current parent scopes; default read-only; one-hour maximum absolute expiry capped
by parent expiry,15-minute idle, monotonic activity checks. Persisted resource,
revocation, disable, expiry and scope changes are rechecked in the same transaction
as create/resolve. Activity cannot refresh absolute expiry.

Domain-separated per-session CSRF primitive required for mutating resolve. A failed
CSRF check does not advance idle. Logout is idempotent and session-only; it works
after parent invalidation but does not revoke the MCP key or sibling sessions.
Session/CSRF secrets do not appear in dataclass repr or persisted rows.
Bounded retained rows (2048global/16owner), atomic concurrent cap enforcement.
These are core primitives, **not** a complete browser HTTP security acceptance.

## Accepted continuation boundary

Root [AGENTS.md](../AGENTS.md), [human handoff](ai-handoff.md), structured
[work-state](work-state.json), README entry and current component registry. CI validates
accepted SHA format/references, current file paths/component status, evidence presence,
next-task separation and mandatory operational constraints; corrupted fixtures fail.
This is structural validation, not independent verification of old VPS reports or
attestation that a pasted SHA truly passed CI. Actions links are the evidence.

## Remaining gates

HTTP same-origin session/cookie/CSRF adapter, login fixation/rotation and abuse,
automatic contact-independent onboarding/renewal/lost-key recovery, reviewed session
cleanup before the16-login lifetime cap becomes real UX, draft/photo form and public
projection, private responses/admin MCP, OS/load and DB+files/security-state recovery.

No default CLI/session wiring, production approval, real credential issuance,
main merge/release or VPS/Caddy/DB change. Pages is documentation only; the
[owner-controlled single-publisher gate](ci-pages.md#remaining-single-publisher-configuration-gate) remains.
[Six major stages to useful external TEST](deployment-readiness.md) are unchanged;
M3b.1 only advances part of the first stage.
