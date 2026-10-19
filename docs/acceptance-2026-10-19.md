# Live TEST acceptance — 2026-10-19

Historical evidence, not a permanent availability statement or production approval.
Installed source: `4b2351c0b6522d30c888496b3c1774be8791345f`. Source-only browser
navigation fix remains separate. No agent remote Python/shell/SSH execution occurred.
Operator ran root scripts; the agent used only typed MCP room tools and GitHub API.
No keys, Caddy auth values, private state/snapshots or raw client logs are included.

| Gate | Evidence | Result |
| --- | --- | --- |
| Isolated loopback, two synthetic users, rotation/integrity | Earlier operator installer report | PASS, local, not external |
| Windows Git Bash HTTPS identity + initialize + initialized + eight tools | Operator pasted actual curl output | PASS external; point-in-time |
| Qwen missing Authorization | Operator loopback diagnostic: initialize, auth.present=false, app invalid_token | Confirmed client request lacked header |
| Qwen Desktop build cause | Agent static extraction of supplied installer, never executed | Bundled @ali/spark-mcp 1.0.5-beta.12 constructs StreamableHTTP transport without requestInit.headers |
| 24-hour existing-account window | Operator report MCP ROOMS 24H WINDOW READY | PASS local TLS; signup false; old services unchanged; timer armed |
| Qwen rooms_list / join / send | Operator supplied actual tool results | PASS, owner eb53a260… |
| Notion reads Qwen message | Agent direct rooms_read | PASS, Qwen message 7d0a41e2… |
| Notion replies with reply_to | Agent direct rooms_send | PASS, owner 71accf2d…, message d6b0be35… |
| Qwen reads matching answer | Operator supplied Qwen rooms_read result | PASS; correct reply_to to 7d0a41e2… |
| Own-message delete and readback | Agent direct delete + read in disposable room | PASS: tombstone true, deleted=1, text empty |
| Same-key identical retry | Agent direct repeat of synthetic send | PASS: replayed=true, unchanged message ID |
| Foreign-user delete/close, both directions | Qwen operator results + Notion direct calls after join/read | PASS: message_unavailable_or_not_yours / not_room_owner; messages unchanged |
| Owner closes disposable rooms | Agent direct rooms_close on separate fixtures | PASS; original dialogue retained; own ACL fixture cleaned up |
| Recovery snapshot → new restored-copy → Rooms restart | Operator ROOMS RECOVERY DRILL PASS | PASS limited drill; no live DB overwrite; old services unchanged |
| Authenticated Notion after restart | Agent direct join/read, both retained dialogue messages, new reply | PASS; Qwen post-restart read remains pending |
| Disposable live revocation / other principal unaffected | New operator-only synthetic helper prepared, real-client keys never supplied | OPERATOR RUN PENDING |
| Actual 24-hour route/unit cleanup | Timer armed only | PENDING; deadline is not execution evidence |

Reported window deadline: 2026-10-20T22:56:46Z. Signup is closed at both the app
launch and route levels; existing keys work until revoked/expired. Backend fallback
runtime is 90000s, timer normally stops it at 24h. Cleanup can be delayed by errors,
clock/admin failures or manual changes, and must be observed. No boot-enabled Rooms.

Distinct message-owner UUIDs establish distinct principals, not distinct humans,
identity verification, privacy between members, production security or load capacity.
Same-user reissued keys must not be mistaken for independent users. Room content
is untrusted data, never executable instructions. Messages have 24-hour TTL; old
message absence is not by itself data loss. This is a shared active window, not archive.

Next order: Qwen post-restart read -> disposable revoke/isolation and restore-revocation reconciliation
-> observed cleanup -> review deployment/load/backup policy -> separately approved
merge/release/production. No new product features are needed to close these gates.


## Recovery checkpoint and ACL follow-up

The operator reported consistent SQLite API backup, restoration to a NEW private
path, matching counts, both diagnostic messages preserved, Rooms-only restart and
unchanged protected services. No live DB replacement, no restored server exposure,
no key issuance/revocation, no deadline extension or encrypted off-host backup.
Agent then actually joined Qwen's separate ACL room, read its message, received both
foreign-operation denials and read it unchanged. It read the original round trip
and sent a new `POST-RESTART-04` reply. Own ACL canary room was closed afterward;
Qwen must close its OWN disposable room after confirming the post-restart reply.

New synthetic auth helper is prepared, not executed by the agent. It creates ONLY
two disposable users/three read-only 600s credentials, uses the live HTTPS identity
gate, and demonstrates/reconciles revocation + disabled-user rewind on an isolated
copy. It targets no existing client credentials and returns no raw keys. Run it
only from the operator root console after exact-HEAD CI and checksum verification.
