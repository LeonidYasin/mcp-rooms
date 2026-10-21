# F3c.1 CI evidence — locked offline wheelhouse

Accepted source: [`fc96fe641092b1cfc07c6fa25cc2d3a65d0a88ac`](https://github.com/LeonidYasin/mcp-rooms/commit/fc96fe641092b1cfc07c6fa25cc2d3a65d0a88ac).
[Contract](operator-package.md). This closes dependency/bundle slice only, not F3c.2 or VPS readiness.

## Exact-source evidence

- [Locked wheelhouse push workflow, attempt1](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39596593802): success. Independently [same-source PR workflow](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39596601366) success.
- Verifier:31 distributions (own project +30 runtime dependencies),16814485 wheel bytes, kind `locked-wheelhouse-not-vps-installer`, expected source matches.
- New clean Python3.12 venv: install uses `--no-index --only-binary=:all: --find-links ... --require-hashes -r install.lock`. No pytest/Qwen packages installed in this runtime venv. `pip check`: `No broken requirements found.` Download/build stages before installation require network; this is offline installation, not an offline build or network-isolation proof.
- Installed-wheel native candidate journey: real synthetic photo through child Landlock/seccomp, MCP consent/public card/withdraw. `CANDIDATE SMOKE PASS`. No sockets/VPS in smoke.
- Installed-wheel DB+native photo recovery to new quarantined path: `RECOVERY SMOKE PASS`. No serving of restored copy.
- [Push CI](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39596593981), [same-source PR CI](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39596601491): matrix3.10–3.13, package/install smoke passed. Python3.12 **789 passed,2 warnings**; Python3.10 **728 passed,42 skipped,2 warnings**.28 new bundle cases over F3b761; native exclusions unchanged.
- [Docs QA/build/deploy](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39596593923):16 diagrams, local links/assets, mobile overflow/search/screenshots passed. Pages remains documentation only; unresolved single-publisher owner configuration gate unchanged.
- Exact-source aggregate inspected:16 success,1 skipped,0 failure/pending. Skip is not a test pass or permission to merge/deploy.

## Trust anchors and artifact

Runtime lock file: `operator/runtime-linux-x86_64-py312.lock`.
SHA256: `05f7fd5ba929c68b25b46649c25a8868834e50834d6cc0ba9addd15e411de536`.

Artifact on push wheelhouse run: `operator-wheelhouse-fc96fe641092b1cfc07c6fa25cc2d3a65d0a88ac-linux-x86_64-py312`, ID12344003808, listed not expired; retention14days.
Inner `bundle.tar.gz`: **16641812 bytes**, SHA256
`337fe170fb1317882d976c045d8adda23a20b671c0c75abf18f6ac5e5631cce4`.
This digest is for inner tar.gz, NOT GitHub artifact's outer ZIP. PR/rebuild archive may differ; never mix run/attempt/digest.

Allowlist: project/runtime wheels, runtime.lock, install.lock, manifest.json, OPERATOR.md.
No state, DB, key, env, photos or private logs. Archive regular files0600, wheel directory0700; explicit allowlist, not recursive checkout.
Verify trusted archive digest first; extract into new private0700 parent, then use trusted exact-source verifier with independently supplied source/lock hash. Manifest/checksum is not a cryptographic publisher signature. Do not execute code obtained only from an untrusted archive to establish trust in that archive.

## Refusals tested

Wrong source/lock/platform, mutated wheel/manifest/install lock, unknown files, aliases,
shared/writable files, duplicate JSON keys/distributions, missing project wheel,
unsafe names, oversized metadata and existing output/archive are refused. Discovery
kind requires explicit diagnostic opt-in and is not accepted as install candidate.
Fresh offline venv cannot fetch a missing wheel from an index.

## Discovery failure retained

Initial source `dd36058d8de2e974261e8dbfa83e6f339623df6b` failed wheelhouse; main test
matrix passed. Diagnostic source `2eb334420a9b7f114e0370253168001f2dbce6a9` identified
Pydantic2.14.1 METADATA133006bytes over128KiB. Separate wheel METADATA cap256KiB
plus regression acceptance/refusal tests; manifest/lock cap stays128KiB.
Discovery source `22a248751e0118b300ddb6cd99e54891edcda921` passed, but was explicitly
not accepted for installation.30 unique normalized exact runtime pins/hashes adopted
in separate accepted-source commit; no auto-upgrade or pip freeze of dev environment.

## Exclusions / next gate

Not a full reproducible OS/build toolchain, SBOM/CVE-clearance certificate, release,
VPS installer, service supervisor or deployment. Python/pip/venv, glibc, kernel and
Landlock availability remain host prerequisites. No automatic online fallback.

F3c.2: reviewed fresh-only plan/install/health/stop/rollback and parent/child/CPU/Tasks/
disk budgets in Actions, isolated user/unit/paths/port. Then separate owner-approved
fresh read-only VPS preflight, loopback install, HTTPS/external acceptance. Each
remote execution requires explicit approval AND special password. No such execution
occurred; no main merge/tag/release/production/Caddy/live DB/real-key changes.
Recovery outputs remain quarantined and cannot be promoted by copying profile markers.
