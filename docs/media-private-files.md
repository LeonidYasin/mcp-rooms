# M2b.2 — private derivative file primitives

Internal opt-in implementation; not a public upload API, media manifest or owner
permission system. [Exact-SHA CI acceptance](ci-m2b2.md) covers only these primitives.
Existing servers do not import/start/migrate this layer automatically.

## Trust boundary

`PrivatePhotoFiles` receives an **operator-controlled fixed root**, never an HTTP
or MCP argument. Root and immediate parent must already be same-user, canonical,
private directories, mode0700. Linux directory descriptors anchor all blob opens;
`O_NOFOLLOW`, exclusive random creation, no shared files and no hardlinks. It does
not chmod/repair existing files or follow client filenames. New files are0600.

The normalizer/worker result is an internal trusted value. Validating its digest,
length and JPEG framing is not full codec or malware validation. This layer accepts
no original filename, URL or arbitrary storage key for creation. Returned
`StoredDerivative` contains a private random blob key, not a public media_id, URL or
access credential. Identical content is not deduplicated across users.

**Never expose `read(receipt)` directly.** A future service must first recheck the
persisted principal, resource, scope, owner, draft state and committed manifest.
No owner ACL is claimed by these filesystem primitives. A user who learns a key
must not gain an API for reading files.

## Commit / crash behavior

1. Under a per-instance thread lock and cooperating-process directory `flock`,
   scan a bounded inventory and enforce file-count/logical-byte limits.
2. Create a new UUID-named JPEG with `O_EXCL`; write bounded bytes, fsync the file,
   close, fsync the directory, then return the internal receipt.
3. A future service re-authorizes and commits the SQLite manifest **after** durable
   bytes. Filesystem + SQLite are not one ACID transaction.
4. Failure before receipt triggers best-effort rollback of only the newly created
   key. Power loss/process crash/cleanup failure may leave a private orphan.
   No automatic deletion/reconciliation is implemented in this slice.

Read opens without following links and without blocking on a FIFO, verifies regular
file, uid/mode/single hardlink/size, reads bounded bytes and checks full digest and
metadata stability. Missing, corrupt or replaced content fails closed; no empty200.
The directory path/inode must still match the pinned descriptor; moved/replaced roots
are rejected. Paths are not returned in DomainError diagnostics.

## Fixed candidate budgets

- At most256 derivative files, total logical size32MiB per configured root.
- Per file2MiB, matching the existing normalizer output ceiling.
- Inventory scan stops after the bounded count; unknown files/unsafe entries block
  writes rather than being deleted or silently ignored.
- Reopen and cooperating instances enforce the same on-disk count/bytes, not an
  in-memory reset. `flock` assumes a local filesystem with Linux lock/fsync semantics.

These are CI candidate values, not tested VPS throughput/capacity. They do **not**
cover filesystem blocks, backup copies, other roots, SQLite/WAL, per-user quotas or
HTTP buffering. A root full of safe orphans remains full until reviewed maintenance.
No lock-wait deadline is implemented here; future admission must not tie up public
request workers waiting on storage locks. Deployment must use local private storage,
not NFS or an unverified FUSE mount.

## Remaining gates

- OS sandbox for the decoder; same-uid malicious processes and privileged operators
  are outside this filesystem boundary. Directory checks are not a namespace sandbox.
- Typed media reservations/manifests in SQLite, owner/revocation checks, per-owner
  budgets and transaction-safe idempotency; caller-supplied receipts are not authority.
- Read/attach on committed manifests, ordered photo preview hashes and fresh consent.
- Orphan/missing-file dry-run reconciliation, retention and DB+files recovery proof.
- Authenticated bounded upload, safe public projection, web/admin interfaces and
  operator-approved TEST deployment. All remain unavailable.

See [overall storage design](media-storage-design.md) and [worker boundaries](media-worker.md).
