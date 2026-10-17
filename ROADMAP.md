# MCP Rooms roadmap

## Source extraction / private-pilot alpha

- [x] Owner approved public repository and MIT.
- [x] Copy focused room storage/maintenance/tests with immutable source provenance.
- [x] New local UUID users and per-connection random Bearer credentials; no GitHub prerequisite.
- [x] Digest-only storage, expiry/revocation/disable/resource/scopes, private-file CLI issuance.
- [x] Eight room tools over official MCP SDK; no other server tools/admin APIs.
- [x] New standalone SQLite application_id; explicit refusal of embedded DB identity.
- [x] Prepare core/recovery/auth/ASGI/admin tests and Python 3.10–3.13 CI/build workflow.
- [ ] Passing exact-HEAD CI and review of source/auth/dependency/licenses.
- [ ] Real header-auth clients (including Notion) and separate operator-approved loopback TEST.
- [ ] Live independent users, revoke/rotate/disable negatives; no public enrollment.
- [ ] Restart/backup/restore drill including auth revocation rewind handling.
- [ ] Disk/WAL/backups budgets, off-host recovery, alerting and measured capacity.
- [ ] Separately approved production release, deploy and rollback.

## Shared core / compatibility

- [ ] Differential embedded/standalone contract fixtures (document intentional identity differences).
- [ ] Canonical versioned core + pinned embedded GitHub compatibility adapter.
- [ ] Separate reviewed identity/data migration; no automatic conversion of existing VPS DB.
- [ ] Agora integration after contract acceptance; market/embedding matching separate from storage.

## Broader onboarding

- [ ] Maintained OAuth 2.1 authorization-server adapter, discovery/PKCE/audience and real client gates.
- [ ] Proven account linking by issuer/subject, recovery/abuse review, independent agent delegation.
- [ ] Private rooms/moderation/public-market security only after an explicit product decision.

No automatic deployment, autonomous agents, endless history, E2EE, A2A, matching or payments claimed.
