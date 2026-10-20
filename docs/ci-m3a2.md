# M3a.2 CI evidence — bounded private photo HTTP

Accepted application source:
[`bca0c8a0ea0336125f928edf196c927a5d6678ed`](https://github.com/LeonidYasin/mcp-rooms/commit/bca0c8a0ea0336125f928edf196c927a5d6678ed).
Later documentation changes are not a new runtime acceptance SHA. This is an
explicit composition option, not a new default CLI/service or live upload URL.

## Application results

- [Push CI, attempt 1](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39501660638): success, Python 3.10–3.13, wheel/sdist and installed-package verification.
- Python 3.12: **539 passed, 2 warnings**. Compared with M3a.1: 38 additional parametrized cases.
- Python 3.10: **489 passed, 31 skipped, 2 warnings**. Optional native worker remains unsupported on 3.10; transport/authorization tests still run there.
- [PR CI](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39501666461) succeeded for the same source SHA.
- [Documentation CI](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39501660446) succeeded: 15 diagrams, local links/assets, mobile overflow, Cyrillic search and screenshots. Documentation deployment is not application deployment.
- Aggregate at inspection: 14 successful checks, 1 skipped, 0 failed/pending; includes documentation/deployment, not 14 separate application suites or merge authorization.

All application tests, real child-worker decode, package builds and ASGI calls ran
in GitHub Actions. Locally only source preparation and AST syntax inspection.
Synthetic users, ephemeral keys and generated fixture images; no real publication,
credentials, listing photo or VPS request. An initial test looked for media IDs at
the wrong nesting level; fixed to the existing `listing.content.media_ids` contract,
without changing the API or removing the assertion. Extra negative cases were added. A final regression also covers TimeoutError during response sending: the outer Bearer gate now tracks response-start and does not try to send a second response after transport failure.

## Accepted boundary

- Default-off upload even with market MCP composed; invalid opt-in config fails before DB creation.
- Shared raw binary HTTP for future browser form and agent file capability.
- Common Host/Origin/query/Bearer checks; persisted scope/ownership/revision before receiving body, then core rechecks.
- Strict MIME/framing/headers, bounded incremental body, disconnect/length/timeout negatives.
- Per-app/process nonwaiting owner/global admission, released on failures and held through response sending; a failed send is not retried with a second response.
- Idempotent media receipt; changed payload conflicts; upload alone does not attach or publish.
- Owner-only derivative GET, route/listing binding, expiry/integrity and revoked-during-file-read failures without returning photo bytes.
- MCP attachment and exact photo preview after HTTP staging; active publication blocks new upload before body.
- Native isolated child normalizes a generated PNG to metadata-free JPEG in CI >=3.11; malformed content rejected.

## Not accepted by this slice

Browser form/session/CSRF, automatic marketplace onboarding/recovery, anonymous
card/photo serving/search, independent private response, separate admin MCP,
OS filesystem/network isolation, fleet admission, VPS CPU/RAM/load profile and
reverse-proxy wire limits, DB+files disaster restore and security-state reconciliation.
No default CLI change, main merge, release, VPS/Caddy/service change or real key issuance.

See [HTTP contract](media-http.md), [six remaining deployment stages](deployment-readiness.md)
and owner-controlled [Pages single-publisher gate](ci-pages.md#remaining-single-publisher-configuration-gate).
