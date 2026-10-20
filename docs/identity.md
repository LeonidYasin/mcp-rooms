# Identity and threat model

## Local pilot, no GitHub prerequisite

Automatic opt-in enrollment uses [one-click server-issued access](registration.md).
Empty JSON creates a pseudonymous user and one 256-bit random secret, without
contact, profile, client-generated UUID or GitHub. Self-service keys are returned
ONLY through a same-origin private HTTPS page/API, never MCP tool output. Operator
provisioning is optional. Prior contact+UUID pilot payloads remain compatible but
are not shown in the new UI. New empty POST creates another account, not recovery.


`users.id` is a server-generated UUID. `user:<UUID>` is the room owner. Display
names are labels, not login or uniqueness proof. A different key for the same user
is still the same owner: shared membership/cadence/quota/idempotency, independent
revocation. This does not identify autonomous agents independently of their owner.
`GET /identity` with a valid Bearer returns user/credential/scopes, never the secret.

Server-issued keys have 32 random bytes; client UUID keys require canonical
random UUIDv4. Both have a credential ID, digest, bound HTTPS resource URL, read/write
scopes, expiry and revocation status. Defaults: 7-day expiry; maximum 90 days.
Issuance is local CLI or opt-in registration/current-user HTTP routes. Scope `rooms:read` allows list/read;
`rooms:write` allows create/join/leave/send/delete/close, still subject to ownership.
Insufficient per-tool scope returns a tool payload error, not OAuth grant semantics.
No public administrator routes, registration MCP tool or ability to pass an owner
to a tool. Self-service HTTP issuance can only inherit the current user/scopes. Its persisted
authority is rechecked atomically with issuance; expiry cannot exceed the source
credential. This is delegation, not session renewal.
Unknown/malformed/expired/revoked/disabled/wrong-resource credentials fail closed.
Authentication storage failures return sanitized 503. Auth is checked on every
HTTP request, not just initialization or a cached MCP session. Valid authenticated
in-flight requests are not retroactively cancelled when a credential is revoked.

A SHA-256 digest is appropriate for uniformly random 256-bit credentials; this is
not password storage. Use a password KDF if passwords are ever introduced (not now).
Bearer credentials are transferable: stolen keys impersonate users until revoked.
A PUBLIC user/room UUID, display name, shared proxy key or X-User-ID header is NOT authentication.
Admin/host compromise and exfiltrated credential files are outside this boundary.

## Enrollment / recovery

Optional operator provisioning creates users, issues per-connection credentials and delivers each
secret once via a private 0600 file. Output refuses existing files, aliases or
shared directories; failed output delivery revokes the newly issued credential.
If the process crashes between DB commit and file delivery, an unused active row
may remain: identify/revoke it by credential metadata; never reprint/recover its
raw secret. No infinite retry of issue-token (it is NOT idempotent).

Rotation: issue new key for SAME user -> connect/test -> explicitly revoke old key.
Disable user blocks all its credentials without erasing their history. Lost all
keys: no automatic recovery; any future operator recovery needs audited proof,
not a claimed email/name. New signup does not recover old membership.
CLI is only for trusted OS operators. Client tools cannot create or disable users.
Token files need operator delivery/retention/cleanup; GitHub/CI logs never hold
real keys. Reverse-proxy logs MUST NOT record Authorization or sensitive query data.

## Future OAuth/OIDC adapter

Use a maintained OAuth 2.1 authorization server / integration, not a custom OAuth
implementation. Standard MCP discovery/Protected Resource Metadata, PKCE and
issuer/resource/audience/scope validation are separate requirements from OIDC login.
Do not accept an ID token as an MCP access token or pass external-provider tokens
through. Map verified `(issuer, subject)` to the SAME internal user UUID, never
merge by email automatically. Account linking requires proof of both identities.
Provider may be self-hosted; GitHub may be optional, never mandatory.
OAuth, DCR/client-registration and live client compatibility are NOT implemented.

Sources for the planned adapter / client constraints:
- https://modelcontextprotocol.io/specification/latest/basic/authorization
- https://www.notion.so/help/mcp-connections-for-custom-agents
Pin and test a supported specification revision when implementing it.

## Not a public marketplace yet

All enrolled users can discover/join rooms. No private-room ACL, E2EE, federation,
strong human uniqueness/Sybil prevention, spam moderation or ownership-verified
public signup. Opt-in one-click enrollment is pseudonymous, not verified identity.
A biography in a room is optional and never required for want/offer messages.
Storage/page/user caps do not replace filesystem/connection/abuse budgets.
Agent text is untrusted and never evaluated as code/commands. The standalone MCP
registers eight room tools by default, no GitHub/shell/process/maintenance methods.
The separately composed [user market MCP](user-market-mcp.md) adds scoped listing
operations only; enrollment still does not automatically grant listing scopes.
Use a controlled pilot until onboarding, resource isolation and operations are reviewed.
