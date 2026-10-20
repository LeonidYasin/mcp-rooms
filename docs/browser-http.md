# M3b.2 — same-origin HTTP bridge браузерной сессии

**CI: [точный принятый SHA и доказательства](ci-m3b2.md). Не форма, не автоматическая регистрация и не live endpoint.**
Дополняет [ядро browser sessions](browser-sessions.md). Явная trusted composition:
`create_app(..., market=adapter, browser_sessions=BrowserSessions(adapter.drafts))`.
Browser schema1 должна быть отдельно initialized; startup только проверяет binding/schema.
Default CLI и app без параметра не получают новых routes/миграций.

## Ограниченная цель

Три операции `/browser/session`: получить отдельную короткую session по **уже
имеющемуся** ключу, проверить её, выйти. Это не замена согласованной простой
автоматической регистрации: marketplace onboarding/renewal/lost-key recovery и
безопасная выдача начальных grants ещё открыты. Новых пользователей/ключей не создаёт,
не требует GitHub/телефон/email и не обещает, что любой новый посетитель уже может войти.

## HTTP контракт

| Method | Credential / body | Результат |
| --- | --- | --- |
| POST | Один Authorization Bearer; JSON `{}` или `{"scopes":["listings:read"]}` |201, отдельная session cookie и safe context/CSRF |
| GET | Только session cookie; body отсутствует |200, user/owner/scopes/absolute expiry/CSRF, без cookie secret/MCP key/credential ID |
| DELETE | Session cookie + один X-CSRF-Token; body отсутствует |200, session-only revoke и удаление cookie |

POST по умолчанию read-only. Допустимо только явно запрошенное подмножество текущих
listing grants родителя; rooms/admin/owner/user_id/TTL из JSON запрещены. Parent
проверяется до body и в transaction создания session. Ключ не возвращается в JSON,
не попадает в cookie сессии/URL/localStorage и не должен логироваться. Будущий UI
может держать введённый ключ только в памяти на время запроса; сам UI ещё не написан.

Cookie `__Host-mcp-rooms-session`: Secure, HttpOnly, SameSite=Strict, Path=/, **без Domain**,
Max-Age не длиннее server absolute expiry. GET не продлевает absolute deadline и не
переустанавливает cookie. На следующем входе всегда новое случайное значение.
POST при уже присутствующей session cookie возвращает409: сначала выйти, не
переключать пользователя/не ротировать session молча. Invalid/expired session в
same-origin GET даёт401 и очищает cookie; logout с известным CSRF работает даже после
отзыва parent. Logout не отзывает MCP ключ/соседние sessions. Квота retained rows
из M3b.1 сохраняется;16 логинов требуют reviewed retention до production UX.

## Origin / TLS / parsing

Обязательны HTTPS в ASGI scope и точный configured Host; localhost-exception обычного
MCP gate здесь не используется. Origin должен точно совпадать с configured origin.
Для GET без Origin разрешена только комбинация Fetch Metadata: same-origin site,
same-origin mode, empty destination. Будущий frontend должен явно использовать
`fetch(...,{mode:'same-origin'})`. Cross-site/same-site/subdomain/navigation не
получают session context. POST/DELETE всегда требуют точный Origin.

Никакого CORS/preflight allowance; OPTIONS405. Forwarded/X-Forwarded-Proto не
используются для доказательства HTTPS. За TLS reverse proxy нужно **отдельно принять**
доверенный edge→ASGI transport setup; текущий default uvicorn(proxy_headers=False)
сам по себе не делает этот bridge готовым к VPS/Caddy. Не включать доверие ко всем
proxy headers и не отключать HTTPS проверку ради удобства.

Один bounded Cookie header, единственное значение session-cookie; дубли отклоняются.
GET/DELETE отвергают Authorization, чтобы не смешивать identities. POST отвергает
уже присланную session cookie. На `/mcp`, `/identity`, agent upload и admin session
cookie **не интерпретируется как authority**: прежняя Bearer authentication остаётся.
Это не запрет любых посторонних Cookie headers на agent route, а отсутствие fallback.
`bs1_` не является MCP Bearer. Query strings запрещены общим gate.

POST body максимум1024bytes, timeout10s, проверка лимита до копирования очередного
чанка. Точный JSON MIME/UTF-8, duplicate JSON members, CL/TE conflict, duplicate CL,
length mismatch, encoding, disconnect и oversized body fail closed. Чтение тела и
SQLite/native operations не происходят в одной длинной transaction.

## Ограничения нагрузки

Один app/process:8 in-flight session requests без очереди, слот держится до отправки
ответа. Fixed 60s login windows:20 total попыток/3 на проверенный credential ID,
таблица owner counters bounded. Failed credentials расходуют global budget до DB auth;
malformed authenticated attempts — owner budget. Это **не anti-bot**, не fleet budget
и не гарантия доступности: атакующий может исчерпать общий лимит. Нужны отдельные
edge/load/DoS/profile решения до внешнего запуска. Retry-After только transient
http_busy/login_throttled, не lifetime cap. Все ответы no-store/nosniff/no-referrer,
нет сырых exception details. Send failure не порождает второй HTTP response.

## Важный следующий security gate

**Cookie ещё не передаётся в listing/media команды.** Их текущий Principal привязан
к parent credential, а не к session row. Если сразу подключить такой Principal к
загрузке/записи, logout session во время body/worker может не остановить последующую
core transaction, пока parent key жив. Нельзя считать повторную проверку parent
полной повторной проверкой browser session.

Следующий M3b.3: backward-compatible trusted session binding с проверкой session
owner/credential/resource/audience/scopes/revoke/absolute+idle expiry **внутри core
transaction авторизации**, включая медленный media I/O. Только после приёмки этой
границы подключать typed browser market actions и общий upload. Автоматический
onboarding/recovery, reviewed retention и затем форма остаются зависимостями web MVP.

Тесты [ASGI session bridge](../tests/test_browser_http.py) — synthetic CI only.
HTTPX cookie jar/ASGI проверки не заменяют реальный browser cookie-policy QA;
это отдельная приёмка перед web-формой/внешним TEST. Нет реальных ключей/публикаций,
HTTP сервера/VPS или cookies пользователей в этих проверках.
