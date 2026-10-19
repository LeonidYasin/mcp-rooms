"""
MCP proxy v2: --debug = безопасная трассировка, не Flask debugger.
Читает список серверов из .env и поднимает их локально на 127.0.0.1.
Подставляет нужные заголовки (X-API-Key, Authorization и т.д.) при форварде.

Зависимости:
    pip install flask requests python-dotenv

Запуск:
    python mcp_proxy.py                     # интерактивное меню выбора сервера
    python mcp_proxy.py --server leonid     # один сервер по имени префикса
    python mcp_proxy.py --server all        # все серверы из .env
    python mcp_proxy.py --server a,b        # несколько через запятую
    python mcp_proxy.py --list              # показать распознанный конфиг и выйти

Формат .env (см. .env.example):
    <PREFIX>_UPSTREAM=https://host/mcp
    <PREFIX>_HEADERS=X-API-Key=...,Authorization=Bearer ...
    <PREFIX>_PORT=8788          # опционально; пусто/нет = авто-порт от 8788
"""

# =============================================================================
# БУТСТРАП КОДИРОВОК — должен выполниться ДО ЛЮБОГО print()
# =============================================================================
import os
import sys

ENC_REPORT = []          # человекочитаемый отчёт о том, что сделали с кодировкой
ASCII_SAFE = False       # True = выводим только ASCII-глифы (для cp1251/cp866 консолей)


def _bootstrap_encoding() -> bool:
    """
    Пытается привести stdout/stderr к UTF-8. Возвращает True, если после всех
    попыток поток ВСЁ ЕЩЁ не может кодировать Unicode -> включаем ASCII-режим.
    """
    report = ENC_REPORT

    # 0) Запоминаем исходные кодировки для отчёта
    orig_out = getattr(sys.stdout, "encoding", None)
    orig_err = getattr(sys.stderr, "encoding", None)
    report.append(f"original stdout={orig_out} stderr={orig_err}")

    # 1) Windows: переключаем кодовую страницу консоли на UTF-8 (65001)
    if os.name == "nt":
        try:
            import ctypes
            k32 = ctypes.windll.kernel32
            k32.SetConsoleOutputCP(65001)
            k32.SetConsoleCP(65001)
            report.append("windows console CP -> 65001")
        except Exception as e:                                   # noqa: BLE001
            report.append(f"windows CP switch failed: {e}")

    # 2) Python 3.7+: reconfigure потоков на UTF-8 с заменой не кодируемых символов
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name)
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
            report.append(f"{stream_name} reconfigured -> utf-8/replace")
        except Exception as e:                                   # noqa: BLE001
            report.append(f"{stream_name} reconfigure failed: {e}")

    # 3) Probe-тест: может ли итоговый поток закодировать Unicode-глифы
    probe = "\u2192\u2022\u26a0"   # -> • !
    enc = getattr(sys.stdout, "encoding", None) or ""
    try:
        probe.encode(enc)
        ascii_safe = False
        report.append(f"probe OK on {enc} -> unicode glyphs allowed")
    except Exception:                                            # noqa: BLE001
        ascii_safe = True
        report.append(f"probe FAILED on {enc} -> ASCII-safe mode")

    return ascii_safe


ASCII_SAFE = _bootstrap_encoding()


def U(uni: str, asc: str) -> str:
    """Возвращает Unicode-глиф или его ASCII-замену в зависимости от режима."""
    return asc if ASCII_SAFE else uni


# =============================================================================
# ИМПОРТЫ ЗАВИСИМОСТЕЙ С ПОНЯТНОЙ ДИАГНОСТИКОЙ
# =============================================================================
_MISSING = []
try:
    from dotenv import dotenv_values
except ImportError:
    _MISSING.append("python-dotenv")
try:
    from flask import Flask, request, Response
except ImportError:
    _MISSING.append("flask")
try:
    import requests as req
except ImportError:
    _MISSING.append("requests")

if _MISSING:
    sys.stderr.write(
        "ERROR: missing dependencies: " + ", ".join(_MISSING) +
        "\nInstall with:  pip install " + " ".join(_MISSING) + "\n"
    )
    sys.exit(1)

import argparse
import socket
import signal
import threading
import time
import json
import re
import itertools
from pathlib import Path

# =============================================================================
# КОНСТАНТЫ И УТИЛИТЫ КОНФИГА
# =============================================================================
DEFAULT_PORT_START = 8788
HEADERS_SEP = ","
HEADER_KV_SEP = "="
SUFFIXES = ("_UPSTREAM", "_HEADERS", "_PORT")


def parse_headers(s: str) -> dict:
    """'K1=V1,K2=V2' -> {K1: V1, K2: V2}. Пустая строка -> {}."""
    out = {}
    for pair in (s or "").split(HEADERS_SEP):
        if HEADER_KV_SEP in pair:
            k, v = pair.split(HEADER_KV_SEP, 1)
            k, v = k.strip(), v.strip()
            if k and v:
                out[k] = v
    return out


def load_servers(env_path: Path) -> dict:
    """
    Читает .env и собирает серверы по префиксу <PREFIX>_UPSTREAM.
    Возвращает {name: {name, prefix, upstream, headers, port|None}}.
    Невалидные записи пропускаются с предупреждением.
    """
    values = dotenv_values(env_path)
    by_prefix = {}

    for k, v in values.items():
        if not v or not isinstance(v, str):
            continue
        for suffix in SUFFIXES:
            if k.endswith(suffix):
                prefix = k[: -len(suffix)]
                if prefix:
                    by_prefix.setdefault(prefix, {})[suffix[1:].lower()] = v

    servers = {}
    for prefix, cfg in by_prefix.items():
        name = prefix.lower()
        upstream = (cfg.get("upstream") or "").strip()

        if not upstream:
            print(f"{U('⚠', '!')} skip {name}: empty UPSTREAM")
            continue
        if not upstream.startswith(("http://", "https://")):
            print(f"{U('⚠', '!')} skip {name}: UPSTREAM must start with http(s)://")
            continue

        port_raw = (cfg.get("port") or "").strip()
        port = int(port_raw) if port_raw.isdigit() else None
        if port is not None and not (1 <= port <= 65535):
            print(f"{U('⚠', '!')} {name}: bad port {port}, will auto-assign")
            port = None

        headers = parse_headers(cfg.get("headers", ""))
        if not headers:
            print(f"{U('⚠', '!')} {name}: no HEADERS defined (upstream may reject)")

        servers[name] = {
            "name": name,
            "prefix": prefix,
            "upstream": upstream,
            "headers": headers,
            "port": port,
        }
    return servers


# =============================================================================
# ПОРТЫ
# =============================================================================
def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def assign_ports(servers: dict, start: int = DEFAULT_PORT_START) -> None:
    """
    Заполняет port=None первым свободным портом >= start.
    Если ручной порт из .env уже занят — предупреждает и тоже заменяет на свободный.
    """
    used = set()

    # Сначала фиксируем ручные порты
    for s in servers.values():
        if s["port"] is not None:
            if s["port"] in used or not port_is_free(s["port"]):
                print(f"{U('⚠', '!')} {s['name']}: port {s['port']} busy/duplicate, will auto-assign")
                s["port"] = None
            else:
                used.add(s["port"])

    # Затем авто-назначение для остальных
    cursor = start
    for s in servers.values():
        if s["port"] is None:
            while cursor in used or not port_is_free(cursor):
                cursor += 1
            s["port"] = cursor
            used.add(cursor)
            cursor += 1


# =============================================================================
# FLASK-ПРИЛОЖЕНИЕ (ФАБРИКА)
# =============================================================================
TRACE_LOCK = threading.Lock()
TRACE_IDS = itertools.count(1)
RPC_METHODS = {
    "initialize", "notifications/initialized", "ping", "tools/list", "tools/call",
    "resources/list", "resources/templates/list", "resources/read", "prompts/list",
    "prompts/get", "notifications/cancelled", "logging/setLevel"
}
ROOM_TOOLS = {
    "rooms_create", "rooms_list", "rooms_join", "rooms_leave", "rooms_read",
    "rooms_send", "rooms_delete_message", "rooms_close"
}
SAFE_ERRORS = {
    "invalid_token", "invalid_origin", "invalid_host", "registration_disabled",
    "rate_limited", "quota_exceeded", "invalid_request"
}


def trace(enabled, **fields):
    if enabled:
        with TRACE_LOCK:
            print(json.dumps(fields, ensure_ascii=True), flush=True)


def make_app(name: str, upstream: str, static_headers: dict, debug=False) -> Flask:
    app = Flask(f"mcp_proxy_{name}")
    app.config["UPSTREAM"] = upstream
    app.config["STATIC_HEADERS"] = static_headers
    app.config["MAX_CONTENT_LENGTH"] = 65536
    app.config["PROPAGATE_EXCEPTIONS"] = False
    # --debug means sanitized request tracing, NOT Flask's interactive debugger.
    app.debug = False

    @app.before_request
    def begin_trace():
        from flask import g
        g.trace_id = next(TRACE_IDS)
        g.started = time.monotonic()
        trace(debug, event="incoming", server=name, request_id=g.trace_id,
              http_method=request.method,
              path=request.path if request.path in {"/mcp", "/health", "/"} else "other",
              query_present=bool(request.query_string),
              client_authorization_present=bool(request.headers.get("Authorization")))

    @app.after_request
    def end_trace(response):
        from flask import g
        trace(debug, event="response", server=name, request_id=g.trace_id,
              status=response.status_code,
              elapsed_ms=round((time.monotonic()-g.started)*1000))
        return response

    @app.route("/mcp", methods=["GET", "POST", "DELETE"])
    def proxy():
        from flask import g
        from werkzeug.exceptions import HTTPException
        upstream_h = dict(app.config["STATIC_HEADERS"])
        for h in ("Content-Type", "Accept", "Mcp-Session-Id",
                  "Mcp-Protocol-Version", "Last-Event-Id"):
            v = request.headers.get(h)
            if v:
                upstream_h[h] = v

        r = None
        session = None
        try:
            body = request.get_data()
            metadata = {"body_bytes": len(body)}
            if body:
                try:
                    rpc = json.loads(body)
                    if isinstance(rpc, dict):
                        method = rpc.get("method")
                        metadata["rpc_method"] = method if isinstance(method, str) and method in RPC_METHODS else "other"
                        params = rpc.get("params")
                        if method == "tools/call" and isinstance(params, dict):
                            tool = params.get("name")
                            metadata["tool"] = tool if isinstance(tool, str) and tool in ROOM_TOOLS else "other"
                    else:
                        metadata["rpc_method"] = "non_object_json"
                except (ValueError, UnicodeError):
                    metadata["rpc_method"] = "not_json"
            auth = next((v for k, v in upstream_h.items()
                         if k.lower() == "authorization"), "")
            scheme, sep, token = auth.partition(" ")
            bearer = bool(sep) and scheme.lower() == "bearer"
            trace(debug, event="forward", server=name, request_id=g.trace_id,
                  static_authorization_present=bool(auth), bearer=bearer,
                  rooms_token_format_ok=bool(bearer and re.fullmatch(
                      r"rm1_[0-9a-f]{32}\.[A-Za-z0-9_-]{43}", token)),
                  session_header_present=bool(request.headers.get("Mcp-Session-Id")),
                  **metadata)
            session = req.Session()
            r = session.request(
                method=request.method,
                url=app.config["UPSTREAM"],
                data=body, headers=upstream_h,
                timeout=(10, 180), stream=True,
                allow_redirects=False,
            )
            if 300 <= r.status_code < 400:
                trace(debug, event="upstream_redirect_blocked", server=name,
                      request_id=g.trace_id, upstream_status=r.status_code)
                r.close(); session.close()
                return Response('{"error":"upstream_redirect_blocked"}',
                                status=502, mimetype="application/json")

            skip = {"content-encoding", "content-length", "transfer-encoding",
                    "connection", "keep-alive", "server", "date", "set-cookie"}
            resp_h = [(k, v) for k, v in r.headers.items() if k.lower() not in skip]
            ct = r.headers.get("content-type", "")
            trace(debug, event="upstream", server=name, request_id=g.trace_id,
                  status=r.status_code, sse=ct.startswith("text/event-stream"))
            if ct.startswith("text/event-stream"):
                trace_id = g.trace_id
                def stream():
                    try:
                        yield from r.iter_content(chunk_size=4096)
                    except Exception as exc:
                        trace(debug, event="stream_error", server=name,
                              request_id=trace_id, error_type=type(exc).__name__)
                    finally:
                        r.close(); session.close()
                        trace(debug, event="stream_closed", server=name, request_id=trace_id)
                response = Response(stream(), status=r.status_code, headers=resp_h)
                response.call_on_close(r.close)
                response.call_on_close(session.close)
                return response

            chunks = []; total = 0
            for chunk in r.iter_content(chunk_size=65536):
                total += len(chunk)
                if total > 4 * 1024 * 1024:
                    raise ValueError("upstream_response_limit")
                chunks.append(chunk)
            data = b"".join(chunks)
            if r.status_code >= 400:
                error = "unclassified"
                if data.strip() == b"Unauthorized":
                    error = "plain_unauthorized"
                else:
                    try:
                        parsed = json.loads(data)
                        value = parsed.get("error") if isinstance(parsed, dict) else None
                        if isinstance(value, str) and value in SAFE_ERRORS:
                            error = value
                    except (ValueError, UnicodeError):
                        pass
                trace(debug, event="upstream_error", server=name,
                      request_id=g.trace_id, error=error)
            response = Response(data, status=r.status_code, headers=resp_h)
            r.close(); session.close()
            return response
        except HTTPException:
            if r is not None: r.close()
            if session is not None: session.close()
            raise
        except Exception as exc:
            if r is not None: r.close()
            if session is not None: session.close()
            trace(debug, event="proxy_error", server=name,
                  request_id=g.trace_id, error_type=type(exc).__name__)
            # Never print exception text: requests errors can contain secret header values.
            return Response('{"error":"upstream_request_failed"}',
                            status=502, mimetype="application/json")

    @app.route("/health")
    def health():
        return {"status": "ok", "server": name}

    @app.route("/")
    def root():
        return {"proxy": name, "endpoints": ["/mcp", "/health"]}

    return app


def run_server(app: Flask, port: int, name: str) -> None:
    import logging
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    try:
        app.run(host="127.0.0.1", port=port, threaded=True, use_reloader=False, debug=False)
    except Exception as e:                                       # noqa: BLE001
        print(f"[{name}] FATAL: {type(e).__name__}", file=sys.stderr)


# =============================================================================
# UI
# =============================================================================
def banner(servers: list) -> None:
    arrow = U("→", "->")
    bullet = U("•", "-")
    print()
    print("=" * 68)
    print(" MCP Proxy - local endpoints for Qwen Desktop:")
    print("=" * 68)
    for s in servers:
        print(f" {bullet} {s['name']:<12} http://127.0.0.1:{s['port']}/mcp")
        print(f"   {arrow} {s['upstream']}")
        print(f"     headers: {list(s['headers'].keys()) or '(none)'}")
    print("=" * 68)
    print(" Ctrl+C - stop")
    print()


def interactive_pick(servers: dict) -> list:
    arrow = U("→", "->")
    names = sorted(servers.keys())
    print("\nAvailable servers from .env:")
    for i, n in enumerate(names, 1):
        print(f"  {i}) {n}  {arrow}  {servers[n]['upstream']}")
    print("  0) all")
    while True:
        choice = input("\nChoose (number/name, comma list, 0=all): ").strip().lower()
        if choice in ("", "0"):
            return names
        parts = [c.strip() for c in choice.replace(";", ",").split(",") if c.strip()]
        picked = []
        ok = True
        for p in parts:
            if p.isdigit() and 1 <= int(p) <= len(names):
                picked.append(names[int(p) - 1])
            elif p in names:
                picked.append(p)
            else:
                ok = False
                print(f"  {U('⚠', '!')} unknown: {p}")
        if ok and picked:
            # сохраняем порядок и убираем дубли
            seen = set()
            return [x for x in picked if not (x in seen or seen.add(x))]


# =============================================================================
# MAIN
# =============================================================================
def main() -> None:
    p = argparse.ArgumentParser(description="MCP proxy with .env multi-server config")
    p.add_argument("--env", type=Path, default=Path(".env"),
                   help="path to .env (default: ./.env)")
    p.add_argument("--server", type=str, default=None,
                   help="server name(s) comma-separated, 'all', or omit for menu")
    p.add_argument("--list", action="store_true",
                   help="print parsed config and exit")
    p.add_argument("--port-start", type=int, default=DEFAULT_PORT_START,
                   help=f"first port for auto-assign (default {DEFAULT_PORT_START})")
    p.add_argument("--enc-report", action="store_true",
                   help="print encoding bootstrap report and exit")
    p.add_argument("--debug", action="store_true",
                   help="sanitized tracing; NEVER logs keys or message bodies")
    args = p.parse_args()

    if args.enc_report:
        for line in ENC_REPORT:
            print(f"[enc] {line}")
        print(f"[enc] ascii_safe={ASCII_SAFE}")
        return

    if not args.env.exists():
        sys.stderr.write(
            f"ERROR: {args.env} not found.\n"
            "Copy .env.example to .env and fill in your keys.\n"
        )
        sys.exit(1)

    servers = load_servers(args.env)
    if not servers:
        sys.stderr.write(f"ERROR: no valid <PREFIX>_UPSTREAM entries in {args.env}\n")
        sys.exit(1)

    assign_ports(servers, start=args.port_start)

    if args.list:
        for n, s in servers.items():
            print(f"{n}:")
            print(f"  upstream = {s['upstream']}")
            print(f"  port     = {s['port']}")
            print(f"  headers  = {list(s['headers'].keys())}")
        return

    if args.server is None:
        chosen = interactive_pick(servers)
    elif args.server.strip().lower() == "all":
        chosen = sorted(servers.keys())
    else:
        chosen = [c.strip().lower() for c in args.server.split(",") if c.strip()]
        unknown = [c for c in chosen if c not in servers]
        if unknown:
            sys.stderr.write(
                f"ERROR: unknown server(s): {', '.join(unknown)}. "
                f"Available: {', '.join(sorted(servers))}\n"
            )
            sys.exit(1)

    to_run = [servers[n] for n in chosen]
    banner(to_run)

    threads = []
    for s in to_run:
        app = make_app(s["name"], s["upstream"], s["headers"], debug=args.debug)
        t = threading.Thread(target=run_server, args=(app, s["port"], s["name"]),
                             daemon=True, name=f"proxy-{s['name']}")
        t.start()
        threads.append(t)

    def shutdown(sig, frame):
        print(f"\n{U('⏹', 'STOP:')} shutting down...")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)


if __name__ == "__main__":
    main()