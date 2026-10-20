# M2b.1 — bounded one-shot photo worker

Internal implementation, not a public upload endpoint. [Exact-SHA CI evidence](ci-m2b1.md)
accepts the resource-containment slice, not the full OS sandbox. No VPS deployment is implied.

`PhotoWorker.normalize` runs the existing optional JPEG/PNG normalizer in a fresh
installed Python module via `-I -B`, never a shell. The stdlib-only supervisor does
not import Pillow. Only declared MIME and bounded image bytes cross stdin; an
explicit minimal environment excludes credentials, proxy variables and PYTHONPATH.
No caller-selected executable, command, path or URL is accepted.

## Candidate limits (not VPS capacity approval)

| Boundary | Fixed candidate |
| --- | --- |
| Platform | Linux, Python >=3.11, optional media extra |
| Input | 8 MiB; streaming transport admission still required before allocation |
| Slots | 2 per reused supervisor instance; immediate busy, no queue |
| Child address space | 512 MiB |
| Child CPU | 3 seconds |
| Supervisor wall deadline | 8 seconds |
| File writes/core dumps | RLIMIT_FSIZE=0, RLIMIT_CORE=0 |
| Descriptors/process creation | NOFILE=32, NPROC=0 (per-user OS semantics) |
| stdout | 2 MiB +2048 bytes, bounded while reading |
| stderr | discarded; no payloads, tokens or decoder tracebacks in logs |

The child sets rlimits before decoder imports. No threaded-parent `preexec_fn`
or process-global limit changes. Parent multiplexes input/output without an
unbounded `communicate()`, kills the process group and reaps the child on exit.
Nonzero exit, timeout, excess output, malformed framing, extra bytes, unexpected
metadata and digest mismatch fail closed. A result is not a media manifest.

The protocol validates exact JSON keys/types, JPEG framing, declared length,
dimensions and SHA-256, **not a second decode in the parent**. These checks cannot
establish safety against a compromised native decoder; an attacker controlling
that child could also manufacture the output. No authenticity claim is made.

## Still required before public exposure

This is **resource containment, not an OS security sandbox**. rlimits do not deny
network access or reading existing files. `NPROC` has per-user/root limitations;
a process group is not a PID namespace. No claim of strong hostile-child isolation.

A dedicated unprivileged worker identity, filesystem/network/namespace isolation,
private temporary directory policy and operator-proven limits remain required.
The process inherits no credentials via environment, but without a filesystem
sandbox existing readable secrets would still be a risk. The installed module and
interpreter must be trusted and immutable to the service identity.

Slots are per instance, not an aggregate cap across application processes. Fleet
admission, HTTP streaming body limits, owner/revocation checks, durable staged
storage, disk/WAL quotas, manifests, preview consent and publication remain separate
work under [storage design](media-storage-design.md). No live route was added;
`media_ids` in draft APIs remain unavailable.

Tests use only generated images and synthetic subprocess failures in GitHub CI.
Fault harness replacement is a test monkeypatch, not a configurable production
command runner. Full OS integration and load tests on VPS remain unperformed.
