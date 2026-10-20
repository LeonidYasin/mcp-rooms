# M1b.1 CI evidence: private list / taxonomy read / archive

Code SHA: `104d5a5cd985582c2c2e5549b68c72b6d63aaea8`.
Branch: feat/standalone-identity, PR #1. No merge, runtime upgrade or production implied.

## Observed

- Exact-SHA aggregated status complete/non-truncated: 8/8 successful checks,
  Python3.10/3.11/3.12/3.13 across push + PR. No failed/pending/skipped checks.
- [Push run attempt 1](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39467967386).
- [PR run](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39467972912).
- Python3.12 push log: **226 passed, 2 warnings in 10.62s**.
- Wheel + sdist build successful, installed-wheel import verification job successful.
- Static preparation: changed Python AST parsed without project imports; 73 relative
  documentation links checked without missing targets. No local pytest or VPS execution.

The previous baseline had 197 tests; this matrix includes the new lifecycle/migration
cases plus the existing suite. The two warnings are not claimed fixed. This is
exact-code-SHA evidence, not an assumption that every later commit already passed.
Documentation-only evidence commits do not alter this tested runtime source.

## What this accepts

Own keyset list with actor/status isolation and strict limits; active-category child
read; terminal private archive; revision and retry atomicity; migration v1→v2 preserving
rows/receipts, explicit version guards and DDL-failure rollback; regression with M1a,
existing room/identity behavior, and distribution packaging. See [contract](private-draft-lifecycle.md).

## What it does not accept

No public listing MCP/HTTP, signup listing scopes, media upload, publication/consent,
private response, web sessions, admin MCP, load/retention/delete readiness, VPS rollout,
real client exchange or actual sale. Archive retains private content and receipt history;
retention/erasure/retry-horizon and reserved protective-operation budgets remain gates.
The synthetic test credentials are not a live auth deployment.
