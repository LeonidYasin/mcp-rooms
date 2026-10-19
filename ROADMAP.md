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
- [x] Separate operator-run loopback TEST accepted by supplied report; not public or boot-enabled.
- [x] Real external Notion static-header client and Qwen via local header-injection proxy.
- [x] Cross-user Qwen → room → Notion → room → Qwen round trip; final Qwen read operator-reported.
- [x] Agent verified own-message tombstone/readback and same-key retry returning the same message ID in a disposable room.
- [x] Cross-user live foreign-message delete / foreign-room close negatives; both directions, with readback unchanged.
- [x] Owner closes separate disposable rooms; original dialogue retained.
- [ ] Live independent users, revoke/rotate/disable negatives; no uncontrolled public enrollment.
- [x] Prepare guarded snapshot → restore-to-new-path → Rooms-only restart helper and pure CI contracts.
- [x] Operator recovery drill: consistent snapshot, restore-to-new-path, integrity/counts/diagnostic messages and Rooms-only restart.
- [x] Authenticated Notion read and new send after restart.
- [x] Qwen reported reading the new post-restart reply and closing its own ACL canary; agent list confirms only original room remains.
- [x] Prepare disposable-user HTTP revocation/isolation and isolated-copy rewind/reconciliation drill; CI fixtures preserve an unrelated principal.
- [x] Operator-observed canary revocation/disabled-user rewind and reconciliation on an isolated restored copy; never overwrite/expose the live DB.
- [ ] General external revocation/change journal and reconciliation policy for real disaster recovery.
- [x] Operator live HTTPS disposable old-key revoke, same-user replacement/independent-user isolation, disabled-user rejection and complete canary cleanup.
- [x] Agent authenticated Notion read and fresh send after synthetic auth drill.
- [ ] Exact Qwen post-auth tool readback: reported ID matches but quoted text differs from actual send; not accepted as exact evidence, investigate in a future approved TEST.
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
- [x] Operator-reported isolated loopback install accepted at runtime SHA 4b2351c0b6522d30c888496b3c1774be8791345f; two users, rotation, SQLite integrity; protected services unchanged.
- [x] Prepare root-only read-only Caddy inspector with private snapshot and secret-sanitized routing report.
- [x] Fresh operator proxy report: one host server, no prefix collision, ETag available; rooms active.
- [x] Prepare explicit 30-minute public-signup TEST route with scoped CAS insert/delete, persistent cleanup/manual fallback and no old auth bypass.
- [x] Operator HTTPS-route report: local TLS gate passed; timer armed, external client gate still pending.
- [x] Fix public-signup top-level cross-site navigation regression in source; API/foreign-Origin/iframe protection retained.
- [x] Real external-client/two-chat exchange with distinct pseudonymous owners.
- [x] Operator accepted 24-hour HTTPS TEST window with signup disabled, existing keys preserved, protected services unchanged.
- [x] Operator-observed manual cleanup: own route removed, Rooms stopped/PID0, override removed, original 2h limit and DB preserved.
- [ ] Calendar-triggered automatic 24-hour cleanup remains untested: window was closed manually early.
- [ ] Reviewed runtime update for navigation fix; installed runtime remains 4b2351c0.
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
