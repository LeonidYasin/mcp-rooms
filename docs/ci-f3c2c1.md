# F3c.2c.1 evidence — fixed unit and real cgroup fixture

Accepted source [`8b7ef9611973ed615f9b59955cfe493659bd8d81`](https://github.com/LeonidYasin/mcp-rooms/commit/8b7ef9611973ed615f9b59955cfe493659bd8d81).
[Contract](operator-supervision.md). This accepts a review renderer and synthetic
supervision experiment, NOT an installer, real candidate-in-systemd or VPS capacity.

## Exact-source results

- [Push CI attempt1](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39610751629), [same-source PR](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39610759661): Python3.10–3.13 matrix success. Python3.12 **903 passed,2 warnings**; Python3.10 **842 passed,42 skipped,2 warnings**.39 added renderer safety/injection cases; warnings not claimed fixed.
- [Push supervision attempt1](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39610751679), [same-source PR](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39610759804): systemd-analyze syntax check and real root-owned ephemeral unit fixture succeeded on a disposable hosted ubuntu24.04 runner. Root was used only inside Actions, not on VPS or through remote process tools. No real credentials/application/profile/DB involved.
- `SYSTEMD SUPERVISION PASS`: cgroup_v2=true, parent_and_term_resistant_child_stopped=true, fixture_only=true, application_tested=false, vps_capacity_accepted=false. Stop took **2.263s** with a2s TERM grace then forced control-group cleanup.
- Push fixture sample: memory.current=memory.peak=**31903744 bytes**; memory.max=134217728; pids.current=2; pids.max=16. Group CPU usage69066 microseconds (user43041/system26025); throttled22189 microseconds. These are one short synthetic fixture sample, not app/native photo benchmarks or VPS resource acceptance.
- [Offline wheelhouse push](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39610751533) and [PR](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39610759744) succeeded; prior offline/native/lifecycle regression checks remain required.
- [Docs QA/build](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39610751589):16 diagrams, local links/assets, mobile overflow/search/screenshots passed. Pages is documentation only; single-publisher configuration gate remains.
- Aggregate **18 success,1 skipped,0 failed/pending**, complete19-check enumeration. Skipped docs job is not a passing runtime test. No merge/deployment authorization implied.

## Discovered and corrected experiment defect

Initial source `f275887414c26412dcd5162ce97286ad3d06e216`
[failed the supervision fixture](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39610308875)
with `fixture_not_ready`; it incorrectly treated a guessed32MiB cgroup RSS floor
as readiness. Do not treat that source as accepted. The corrected fixture writes
an explicit private runtime readiness marker **after** installing its TERM handler
and allocating its child buffer. Readiness no longer depends on an RSS guess.
The accepted source measures cgroup counters independently from readiness and
proves both known fixture PIDs are no longer runnable and the cgroup has no tasks.
This is not evidence of behavior under arbitrary crash/race/hostile process cases.

## Boundaries and next work

Renderer is pure review output: fixed service identity, root-release/state layout,
strict source/resource validation, no arbitrary command, no autostart or host effect.
Provisional candidate limits1GiB/64tasks/100%CPU are not adopted host capacity.
Syntax verification substitutes a synthetic executable because real candidate
release paths intentionally do not exist. The real fixture uses a different
DynamicUser unit and reduced limits; it is NOT the actual candidate unit.

F3c.2c.2 remains: fresh-only root-owned immutable installation wrapper, loaded-unit/
drop-in/path identity checks immediately before effects; actual installed candidate
with native photo processing under the reviewed unit; aggregate resources,
timeout/admission/disk acceptance; interruption and unrelated-service protection.
Separate real-key bootstrap and stop-only rollback must preserve live state.
Then owner-approved VPS preflight → loopback → HTTPS. Every remote execution needs
separate approval AND special password. No main/release/VPS/Caddy/live DB changes,
real credential issuance, public listing or recovery promotion performed here.
