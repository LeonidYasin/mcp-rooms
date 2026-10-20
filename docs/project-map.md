# Project map

```text
Notion personal static-Bearer connection ──────────────────┐
Qwen Desktop → local loopback header adapter (.env secret) ├→ HTTPS /rooms-test/mcp
                                                        │   → scoped Caddy route
                                                        └──→ loopback :8765
                                                            → official MCP SDK
                                                            → BearerGate / local UUID
                                                            → room membership/ownership
                                                            → private standalone SQLite
```

- `src/mcp_rooms/server.py`: SDK tool registration and HTTP Bearer/Host/Origin gate;
  eight tools only. Admin, credential issuance and maintenance are not MCP tools.
- `identity.py`, `enrollment.py`, `signup_page.py`: digest-backed credentials,
  explicit opt-in signup. Latest TEST window is closed; no profile,
  phone/email/GitHub is required for want/offer messages.
- `store.py`: shared rooms, membership/owner rules, text/reply/idempotency/TTL/cadence.
- `admin.py`, `maintenance.py`: non-root service-user operator CLI; consistent
  snapshot/verification, never automatic live-DB replacement.
- `deploy/vps_install_test.py`: initial isolated install, not rerun for an existing TEST.
- `deploy/vps_https_route.py`: legacy 30-minute public-signup route, not current default.
- `deploy/vps_rooms_window_24h.py`: operator-accepted longer existing-account window;
  scoped CAS route, persistent cleanup, runtime-only override, no production restart.
- `deploy/vps_rooms_recovery_drill.py`: operator-reported snapshot/copy/restart PASS;
  no key issuance/revocation or restored-copy exposure.
- `deploy/vps_rooms_auth_drill.py`: operator-reported synthetic HTTP revocation
  and isolated canary restore-rewind/reconciliation PASS; general DR journal remains open.
- `tests/`, `.github/workflows/ci.yml`: Linux Python 3.10–3.13 tests/build; CI does
  not operate the VPS, access real credentials or prove external-client acceptance.

Identity is `user:<UUID>`; clients with one user's keys share ownership and cadence.
Room text is untrusted. Shared means visible to enrolled users, not a private chat.
Client reads are explicit: no background polling, push or autonomous agent execution.

Operational truth: [acceptance](acceptance-2026-10-19.md). Remaining gates:
[roadmap](../ROADMAP.md). Canonical-core extraction and pinned embedded GitHub
adapter come later; the old mcp-server installation/data are not switched. Agora
want/offer/search/matching and provider-independent embeddings remain product phases,
not reasons to add PostgreSQL, new identity requirements or another connector now.


## Saved desktop clients and proposed web market

`clients/qwen/` now contains the delivered local adapter/check, safe .env example,
key-free JSON and usage instructions. They run on the user's PC, not inside the
Rooms server; they do not reopen the stopped TEST or add server runtime dependencies.

[Web market direction](web-marketplace-plan.md): open to all locations, C2C goods/services
first, rides/delivery later. [Detailed mindmap](product-mindmap.md) and
[component / trust / entity graphs](architecture-graph.md) define the next phase.
[Admin MCP](admin-mcp-design.md) is a separate designed boundary, NOT an enabled tool.

New isolated slice: pure `listing_contract.py` and CI fixtures; static responsive
`web/prototype/index.html` with demo/empty/modal states. No storage migration, new MCP
methods/scopes, live web, private negotiation or admin endpoint implemented yet.
[First-sale criteria](first-sale-acceptance.md) require a real item/photos/consent and
independent discovery/reply; no automatic publication of old enrolled-only rooms.
