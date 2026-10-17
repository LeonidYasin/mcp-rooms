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
- [ ] Live independent users, revoke/rotate/disable negatives; no uncontrolled public enrollment.
- [ ] Restart/backup/restore drill including auth revocation rewind handling.
- [ ] Disk/WAL/backups budgets, off-host recovery, alerting and measured capacity.
- [ ] Separately approved production release, deploy and rollback.

## Automatic signup and VPS preparation

- [x] One-click signup with empty JSON: no contact, questionnaire, GitHub or client UUID; not implicit tools/list signup.
- [x] One 256-bit server key shown once; stable user UUID separate from secret, digest-only storage.
- [x] Legacy pilot contact+UUID API compatibility; no required UI fields or contact-based recovery.
- [x] No automatic signup retries; new POST creates a new user, not recovery. Double-click guard and explicit lost-response warning.
- [x] Same-user scoped credential issuance and explicit current-key revoke via protected HTTP, not MCP tools.
- [x] Profiles/biographies optional room content only; want/offer exchange needs no personal data.
- [x] Persisted global signup caps and additive standalone v1->v2 migration, snapshot coverage.
- [x] Prepare read-only operator VPS preflight, isolated unit EXAMPLE and staged TEST plan.
- [x] Operator supplied clean read-only VPS preflight: Python 3.12.3, port 8765 free, no existing candidate user/path/unit; not installation authorization.
- [x] Prepare checksum-pinnable new-service installer, conservative data-preserving rollback and pure/mocked/ASGI acceptance coverage.
- [ ] Operator-run installation with fresh preflight and real service-user/systemd sandbox acceptance.
- [ ] Proxy access/anti-abuse policy, separately approved temporary route and live signup/client gates.
- [ ] Ownership-verified recovery/moderation/Sybil control before broad public onboarding.

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
