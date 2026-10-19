# Qwen Desktop compatibility — static-header TEST

The supplied Windows installer was:
https://download.qwen.ai/windows/x64/Qwen-1.0.3.44-release-win-x64.exe

Agent downloaded and statically extracted it, never executed it. Installer SHA-256:
`393e4669402e48f3fa6cffd0ebaadfe597b06fb26a11b6aaf03f7ee74df26e60`.
Packaged app reports 1.0.3; the GUI had shown 1.0.0. This is NOT proof about Qwen
Code CLI or every future Qwen Desktop build. Do not substitute Qwen Code httpUrl
instructions for the observed desktop form's streamable-http/url schema.

In packaged `@ali/spark-mcp` 1.0.5-beta.12, `dist/cjs/Proxy.js` constructs
`StreamableHTTPClientTransport(new URL(sseURL))` without options. The bundled SDK
reads custom headers from `opts.requestInit.headers`. SSE is also constructed without
header options; switching transports is not an evidenced fix. The main process uses
this Proxy. The operator's loopback capture independently observed no Authorization
on Qwen initialize. This explains the observed invalid_token without weakening Caddy.

The operator's existing local .env proxy can supply Authorization itself:

```dotenv
ROOMS_UPSTREAM=https://leonid-mcp.duckdns.org/rooms-test/mcp
ROOMS_HEADERS="Authorization=Bearer REPLACE_LOCALLY_WITH_CHECKED_KEY"
ROOMS_PORT=8790
```

Qwen connects to `http://127.0.0.1:8790/mcp` (actual port from the proxy banner),
StreamableHTTP, no secret in the Qwen configuration. Only loopback is HTTP; remote
hop verifies HTTPS. Keep canonical upstream; no token in URL, chat or MCP arguments.
The delivered mcp_proxy_v2 adds sanitized --debug tracing, never Flask debug=True,
and blocks upstream redirects. It and the read-only check are now saved in
[clients/qwen](../clients/qwen/README.md), with placeholder .env, dependencies and
key-free Qwen JSON. Exact delivered script bytes/checksums are preserved. Client
requirements are NOT server runtime dependencies. CI uses a mocked upstream; this
is not an independently audited production gateway or a Windows GUI certification.

Expected trace: client_authorization_present=false, static_authorization_present=true,
bearer=true. Token-format success is not authentication success; require upstream
initialize200, initialized202 and tools/list200, then actual rooms_list. Logs must
omit header/cookie/session values, tool arguments and message text. Do not request
raw debug logs or screenshots containing secrets. Anyone able to access the local
proxy can act with its configured credential: bind only 127.0.0.1, protect .env,
stop it after testing. Qwen source also contains console.log(config); old logs may
contain configuration. Consider rotation after verified replacement; never revoke
the only working credential first.

Distinguish app JSON `invalid_token` from old Caddy plain `Unauthorized` after the
temporary route disappears. Compare fresh curl and Qwen inside the SAME open window.
Do not fix expired routing by reissuing keys, reinstalling the service or disabling auth.
Real cross-user round trip passed; see acceptance-2026-10-19.md. Future native-header
Qwen fixes need their own capture/acceptance, not assumed compatibility.


## Current availability

The TEST route was manually removed and Rooms stopped, with original 2h unit and
no runtime override. This repo does not provide a permanently open production Rooms.
Start the local adapter only after an operator-approved reachable upstream exists;
it cannot itself reopen the server. Do not respond to normal offline status by
reissuing keys or disabling authorization.
