# Temporary HTTPS TEST route — prepared, not opened by publishing code

Operator reported a fresh non-truncated Caddy report: exactly one expected-host
server, no /rooms-test prefix, ETag supported, rooms unit active at source
4b2351c0b6522d30c888496b3c1774be8791345f; old protected PIDs unchanged. The user
approved preparing an external HTTPS address. No route is created by GitHub/CI.

## Explicit operator action

Checksum-pin `deploy/vps_https_route.py`, then run as operator root with
`--open-30m`. No agent remote run_python/run_command/SSH/background execution.
Fresh checks require the existing new rooms unit active with >35 minutes left,
expected user/workdir/runtime/source, expected host-only HTTPS listener, no prefix
collision/regexp ambiguity and no access/global logging config needing review.
Do not silently restart rooms if its two-hour limit has expired.

The helper arms a persistent systemd calendar cleanup timer BEFORE a conditional
PUT of ONE new top-level host+prefix route. ETag/If-Match prevents stale writes.
It does not POST /load, patch a whole configuration, edit Caddyfile, restart old
services, open firewall ports, change user/database/keys or renew runtime limits.
It creates its own root-private state/script/baseline evidence and unique cleanup
service/timer files; systemctl daemon-reload and enable apply only to cleanup timer.
Root-private baseline can contain existing Caddy secrets: NEVER paste/upload it.

Route:
- https://leonid-mcp.duckdns.org/rooms-test/signup — one-click access page;
- https://leonid-mcp.duckdns.org/rooms-test/mcp — canonical MCP endpoint;
- only exact app paths/methods for signup JS, register, identity and current-user
  key issuance/revocation; unexpected paths remain 404, never fall through old MCP;
- prefix stripped before forwarding to 127.0.0.1:8765; NO old X-Api-Key matcher
  copied or weakened. MCP itself requires its own individual Bearer credential;
- 64 KiB proxy request cap (register remains 4 KiB at app), backend dial/read/write/
  response-header timeouts, max 8 backend connections. These are NOT per-source
  rate limits, frontend connection limits or comprehensive DoS protection.

## Exposure and expiry limitations

During this short test, signup is PUBLIC to anyone knowing/discovering the URL.
There is no shared signup password, questionnaire, phone, email or GitHub login.
Global app quotas limit growth but attackers can consume signup quota; no anti-bot,
Sybil protection, privacy between enrolled users or production security is claimed.
Rooms are shared with enrolled users. Same-host apps share browser origin trust;
this is a controlled TEST, not a broad marketplace launch.

A persistent calendar timer attempts removal after 30 minutes, with retries on
failure and manual cleanup command in the result. It is NOT a hard security expiry:
clock/admin outages or concurrent/changed route state may delay cleanup. No promise
that time alone always deletes config. Rooms' separate 2-hour runtime is not extended;
reboot does not boot-enable rooms. Caddy may autosave runtime API changes; Caddyfile
is not edited. On reboot, persistent cleanup retries; do not rely on transient timers
or restore an old whole-config snapshot. Verify actual removal, not just scheduling.

## Acceptance and cleanup

Local TLS gate connects to 127.0.0.1:443 with certificate-verified SNI/Host matching
the public hostname. Checks signup/no-store, JS, unauthenticated MCP/identity 401,
invalid registration 400 (no user created), unknown method path 404 and old unauth
boundaries 401. Old selected service states and Caddyfile hash are compared. Only
our insertion is allowed in the immediate config diff. This does NOT establish
external network reachability, authenticated MCP client compatibility or two-chat
acceptance. The helper NEVER obtains/prints a real user key or registers an account.

Cleanup reloads FRESH config+ETag, locates unique own @id, requires exact route
identity and conditionally deletes just that array item. Concurrent unrelated
changes are kept, never overwritten. A changed/duplicate own route, or a prefix
without its expected marker, requires manual review rather than force-removal.
After confirmed removal, delete only hash/content-matching own cleanup unit files.
Do not stop the currently running cleanup oneshot from inside itself. Keep private
state/evidence and preserve all room/user data. Caught setup/gate failures attempt
this same conservative cleanup. Interrupted processes still require checking state.

## Using the connection

After successful operator report, open signup in your own browser, save the key
privately, and add the canonical MCP URL with that individual Bearer credential.
Never paste keys into a room, chat, URL or issue. One personal connection can be
used by two chats as the SAME user; messages share room_id, not chat identity.
Different users need distinct registration keys. If Notion refuses duplicate URL
connections for an independent-user test, a separately reviewed second alias can
point to the same process/database; no second server or profile is required.
Static-header client support is still a LIVE gate; no OAuth discovery is fabricated.

Implementation sources: Caddy API https://caddyserver.com/docs/api (scoped PUT/
DELETE, ETag/If-Match), transport JSON fields in upstream
https://github.com/caddyserver/caddy/blob/master/modules/caddyhttp/reverseproxy/httptransport.go.
CI lifecycle tests are pure/mocked: no real Caddy/systemd/network/VPS mutations.
