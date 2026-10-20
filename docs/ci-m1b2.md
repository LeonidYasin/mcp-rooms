# M1b.2 CI evidence: exact private preview / publication intent

Code SHA: `2108b93e92e66cf34dd95a4c27721bbacffe4336`.
Branch: feat/standalone-identity, PR #1. Runtime was not deployed or merged to main.

- Complete exact-SHA aggregated checks: **8/8 success**, Python3.10–3.13, push+PR.
- [Push run, attempt 1](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39469654374).
- [PR run](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39469665301).
- Retrieved Python3.12 log: **247 passed, 2 warnings in 7.37s**. Warnings not claimed fixed.
- Wheel/sdist built, installed-wheel imports include preview_contract.
- Static preparation: Python AST parsed without execution; 83 local doc links checked,
  no missing targets in the checked set. No project tests/imports ran locally or on VPS.

## Accepted scope

Canonical private preview binds exact record/revision/category path/resource/notice.
Separate listings:publish scope checked against persisted credential and trusted
Principal. Intent is private, max5min and bound to draft expiry; receipt replay does
not extend validity. Fresh intent read rejects edits/archive/taxonomy/resource changes,
expiry and revoked access. Synthetic rollback and concurrent retry cases passed with
existing draft/lifecycle/room/identity regression.

This does NOT prove human screen review, actual one-time consumption/publication,
media readiness, external HTTP/MCP interfaces, enrollment of listing credentials,
web sessions/private replies/admin MCP or production. Old intent notice explicitly
states publication disabled; future live-publication schema cannot reuse this approval.
[Contract and limitations](publication-intent.md).

## Positioning and repository metadata

README/package description updated in this working branch. About update via MCP
received GitHub403; readback still showed the old room-only description. Therefore
About is **not updated**, not a successful metadata change. See [desired text and
manual/browser options](project-positioning.md). No homepage/topic changes were made.

The real toilet stays a technical use case; a public launch hero is not chosen and
no real item is published. This evidence describes the specified code SHA; later
document-only commits do not change its tested runtime source.
