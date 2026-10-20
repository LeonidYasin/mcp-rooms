# M2b.3 — owner-authorized private media staging

Internal opt-in service; not HTTP/MCP registration, attachment or publication.
[Exact-SHA CI acceptance](ci-m2b3.md) covers this internal staging slice. No live
schema migration or new scope issuance is implied.

## Contract and boundaries

`MediaStageStore` reuses the persisted credential checks of `DraftStore` with
`listings:write` for staging/retry, `listings:read` for owner reads. Principal must
come from a real authenticating adapter, never a JSON user ID. Current enrollment
still issues rooms scopes only; synthetic CI fixtures seed listing scopes directly.

A derivative is linked to an existing owned, editable, live draft, exact revision,
credential audience/resource and fixed normalization policy. Category ancestry must
remain active. A private opaque UUID media_id is distinct from the private blob key;
responses never return a filesystem path or blob key. Guessed IDs do not authorize reads.

Initialization explicitly adds independent version1 `media_stage_schema` and
`media_stages` tables to the existing snapshot database. It requires market schema2;
partial/future namespaces fail closed. Room schema/application_id/user_version are
unchanged. Neither current server startup nor an HTTP request creates these tables.

## State machine / transaction boundaries

```mermaid
sequenceDiagram
  participant A as Authenticated internal caller
  participant D as SQLite staging
  participant W as Decode worker
  participant F as Private files
  A->>D: authorize, owned live draft + revision, request digest, reserve quota
  D-->>A: RESERVED + opaque media_id
  Note over D,W: No SQLite transaction held during decode or file I/O
  A->>W: bounded original bytes + MIME
  W-->>A: normalized JPEG
  A->>F: exclusive durable file write
  F-->>A: internal receipt, no public URL
  A->>D: recheck credential, resource, draft revision/state, category, TTL and policy
  D-->>A: commit STAGED or refuse
  Note over D,F: Failure can retain a private failed/orphan derivative
```

`RESERVED → STAGED` or `RESERVED → FAILED`. File durability precedes the STAGED
transaction; SQLite and the filesystem are not one ACID transaction. On ordinary
exceptions the service best-effort marks only its already-reserved upload FAILED,
retaining a known derivative key for later reconciliation. A crash may leave a
RESERVED row or private orphan. No best-effort destructive deletion of arbitrary
files is attempted by this service.

Every replay rechecks current persisted rights first. The request digest binds
original byte SHA-256/length, MIME, draft/revision, policy and audience. Same owner
+ client UUID with different data conflicts. Completed retry checks stored-byte
integrity, returns the same media_id/expiry and does not decode or write again.
Pending retry immediately returns `media_upload_pending`; no second worker is
started. Failed retry returns a stable failure and never silently retries work.
Expired reservations/results are unavailable and cannot extend their lifetime.

Reads authorize before opening the file and re-authorize after bounded integrity
I/O, checking the manifest is unchanged. Revocation, disability, audience mismatch,
scope loss, expiry, archive/revision/category changes fail closed. The final read
transaction is the authorization linearization point; no impossible guarantee is
made about a revocation occurring after that check and before network delivery.

## Candidate admission budgets

- Global128 rows /32MiB reserved derivative bytes.
- Per owner16 rows /8MiB reserved derivative bytes.
- Each operation reserves the maximum2MiB derivative budget before decoding.
- TTL10 minutes, capped by draft expiry, never extended on retry.

All rows, including failed and expired ones, keep admission budget in this slice.
This conservative lifetime budget prevents failed/orphan bytes bypassing quotas;
it is **not** a complete rolling upload service. New attempts can exhaust it and
remain blocked until reviewed lifecycle maintenance exists. Under these byte caps,
actual concurrent/lifetime operations may hit the byte budget before the row cap.

Physical file count/bytes are separately checked by the file layer; per-owner DB
budgets do not replace root/disk/WAL budgets. HTTP streaming/admission/time limits,
OS filesystem/network sandbox and fleet concurrency remain separate gates.

## Explicit non-goals / next slice

Photos are **staged, not attached**. They do not mutate a draft revision/content or
preview and cannot be published. Draft APIs still reject `media_ids`; old consent
intents remain invalid for any future live publisher. Existing text drafts remain
compatible. A draft revision change conservatively makes this staged result
unavailable: future attachment needs a new versioned transaction, not a bypass.

Still required: attach/idempotency/revision and ordered media preview hashes;
reviewable reconciliation/retention and DB+files recovery; safe budget reclamation;
authenticated upload/read adapters and actual user scope issuance; explicit consent
and public projection; separate admin controls; operator-approved OS sandbox TEST.
No VPS, main, Caddy, real key or production service changed in this implementation.
