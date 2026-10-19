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
| Foreign-user delete/close, both directions | Disposable canaries prepared | PENDING, not inferred from round trip |
| Owner closes disposable room | Not yet run; room retained for ACL test | PENDING |
| New recovery/restart helper | Source + pure CI contracts prepared | OPERATOR RUN PENDING |
| Disposable live revocation / other principal unaffected | Not yet run in this external window | PENDING |
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

Next order: disposable ACL negatives -> recovery/restart operator report -> real
client recheck -> disposable revoke/isolation and restore-revocation reconciliation
-> observed cleanup -> review deployment/load/backup policy -> separately approved
merge/release/production. No new product features are needed to close these gates.
