# M1a: exact-code-SHA CI evidence

Code SHA: `784b4c6b2834246b34b15d2bcc67140606dc71b8`.
Branch: `feat/standalone-identity`, PR #1. No main merge/deploy implied.

## Observed evidence

- Exact-SHA commit status returned complete/non-truncated: 8 successful check runs,
  0 failed/pending/skipped/neutral; push + PR matrices, Python 3.10/3.11/3.12/3.13.
- [Push run, attempt 1](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39352803859).
- [PR run](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39352808222).
- Retrieved Python 3.12 push-job log: **197 passed, 2 warnings in 3.91s**;
  wheel and sdist successfully built. The two warnings are not claimed resolved.
- Completed jobs include outside-source-tree installed-wheel import verification
  of server/identity/listing contract/new domain and DraftStore.
- Static preparation: AST parsed 6 changed/new Python files without imports or
  execution. 62 local documentation links checked, no missing targets in that set.

CI status success is checked separately from log grep; absence of errors in a log
snippet is not used as proof. No project tests ran on the agent computer or VPS.
Documentation-only evidence commits after this code SHA do not change the runtime
source tested here; their checks must still be read separately if reporting HEAD CI.

## Scope accepted at this level

Opt-in market namespace + initial categories; private persistent draft create/get/
update; persisted principal/credential/resource/scope checks; revision/retry atomicity;
synthetic concurrency/rollback/owner/expiry/quota negatives; legacy room/identity test
regression and package build. Details: [storage design](draft-storage-design.md).

Listing credentials were seeded ONLY in isolated tests. Current production-style
IdentityStore issuance still rejects listing scopes, and there is no user-facing
listing HTTP/MCP route or automatic market startup migration.

## Not accepted by this evidence

Public browsing/publish/media/sessions/private replies/admin MCP, complete conformance
IDs over real transports, load/capacity, backup of new resources under real conditions,
VPS rollout, new user enrollment, production or successful sale. Next: M1b from the
[delivery plan](delivery-plan.md), not public exposure of this internal storage class.
