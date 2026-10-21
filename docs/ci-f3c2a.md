# F3c.2a CI evidence — read-only operator proposal

Accepted source [`0927c82a7370b194a194d552a4cae8ee6486428a`](https://github.com/LeonidYasin/mcp-rooms/commit/0927c82a7370b194a194d552a4cae8ee6486428a).
[Contract and limits](operator-plan.md). This accepts a proposal generator, NOT
operator lifecycle implementation, current host attestation or a VPS installation.

## Exact-source checks

- [Push CI attempt1](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39603773191) and [same-source PR CI](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39603780766): matrix3.10–3.13 success, build/install/native candidate+recovery smoke.
- Python3.12 **826 passed,2 warnings**; Python3.10 **765 passed,42 skipped,2 warnings**.37 new proposal cases; existing native-only exclusions unchanged.
- [Locked wheelhouse and real-verifier proposal integration](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39603773642), [same-source PR](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39603780342): success.
- `OPERATOR PLAN SMOKE PASS`:7 typed stages, host_probe=false, installed=false, synthetic-unattested observations. Plan SHA256 `67202e80a605591deb8a5e8fa9860b125dd8ff27343ad2ab9376ec67230377da` for this exact synthetic fixture/source; not a deploy token.
- Real bundle reverified:31 distributions,16814530 wheel bytes; runtime lock hash unchanged `05f7fd5ba929c68b25b46649c25a8868834e50834d6cc0ba9addd15e411de536`. Inner tar.gz16641867bytes SHA256 `84af58de79c9fab6eee912d7843d9b6157dc51f7b187b47a747d212ae97eaec2`, push run above/attempt1 only. Not hash of GitHub outer ZIP, not reusable across rebuilds. Public-only bundle retention14days; no state/keys/observations uploaded.
- Same workflow then installs new venv with no-index/only-binary/require-hashes; `No broken requirements found.`, `CANDIDATE SMOKE PASS`, `RECOVERY SMOKE PASS` on installed real native photo path. These later application tests are separate from pure plan generation.
- [Docs QA/build/deploy](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39603773249):16 diagrams, local links/assets, mobile overflow/search/screenshots passed. Pages documentation only, single-publisher owner configuration gate unchanged.
- Aggregate16 success,1 skipped,0 failed/pending. No merge or rollout permission.

## What is accepted

Trusted exact-source wheelhouse verification before deterministic proposal; fixed
candidate user/group/unit/release/state/loopback port; canonical HTTPS resource;
strict observation shape/types/prerequisites; conflicting targets and metadata/
trust-anchor failures refused without fallback. Known low/unknown RAM never turns
into accepted capacity. Proposal states no host probe, authorization or measured
resource acceptance; digests bind bytes, not truth/currentness/owner approval.
Input not mutated; no app import/process/socket/fs mutation/credential read.

Seven typed stages contain future requirements, not arbitrary argv/shell commands.
Fresh rollback means stopping only the new unit while preserving state, not
rolling back DB/revocations or restoring quarantined snapshots. Installer must
recheck current host/target/process identity immediately before every effect;
old JSON observation cannot establish absence or prevent TOCTOU.

## Remaining F3c.2b / infrastructure gates

No actual install/start/health/stop/rollback code or root unit applied by this slice.
Implement/test lifecycle interruption, existing/stale identity refusal, state and
unrelated-service preservation; measure combined parent/child/timeout/admission/
disk budgets in Actions before proposing real host limits. Then separately
approved fresh VPS preflight, loopback TEST, HTTPS/external checks. Special password
AND explicit approval per remote execution. No such remote operation performed.
No main merge/release/tag/live DB/real keys/Caddy/production changes. Recovery
promotion and browser writes remain paused gates, not silently accepted.
