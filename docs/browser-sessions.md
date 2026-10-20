# M3b.1 — отдельное ядро браузерных сессий

**CI: [точный принятый SHA и доказательства](ci-m3b1.md); не web login, не форма и не production.**
[Следующий слой после private HTTP upload](media-http.md). Отдельный credential
namespace `bs1_…`, не MCP `rm1_…`; digest-only SQLite storage в той же private DB.
`BrowserSessions(drafts).initialize()` — явная additive browser schema1, без
изменения room/market/media/publication schema. В default app/CLI не подключён.

## Модель доверия

Trusted future login adapter сначала проверяет настоящую credential/identity,
затем передаёт Principal в `create`. Actor/scopes/user_id не брать из JSON клиента.
Этот срез не добавляет обязательную ручную регистрацию: безопасный автоматический
onboarding/возврат пользователя/выдача marketplace grants — отдельный открытый gate.
Долгоживущий MCP ключ не должен храниться в JS, localStorage, URL или cookie сессии.

Session scopes — явное подмножество listing grants родительского ключа; default
только listings:read. Ни rooms, ни admin, ни elevation. Snapshot и persisted grants
проверяются в одной transaction с созданием session; parent expiry ограничивает
срок. На каждом resolve снова проверяются credential/resource/revoke/disabled/scopes.
Новая привилегия у parent не расширяет уже созданную session автоматически.

Абсолютный максимум1час, idle15минут, deadline не продлевается при активности.
Результат содержит отдельно cookie secret и безопасный контекст. Секрет/CSRF
исключены из dataclass repr; в DB только SHA-256 cookie digest. Приложение всё равно
не должно логировать эти значения или сериализовать dataclass целиком в HTTP.

## CSRF и logout

Для mutating resolve нужен отдельный domain-separated HMAC CSRF token, привязанный
к конкретной session. Его можно восстановить сервером из присланной HttpOnly cookie
и вернуть через строго same-origin bootstrap, не раскрывая сам cookie secret.
Сравнение constant-time; чужой/пустой/неверный токен отклоняется без обновления idle.
Сам по себе этот primitive **не полная CSRF защита**: HTTP adapter ещё должен проверять
точный Origin, Host, Content-Type, Fetch Metadata, метод и запрет CORS/query secrets.
Значение mutating задаёт сервер по операции, не клиентское поле.

Logout требует session possession+CSRF, идемпотентно отзывает **только эту session**,
не MCP ключ и не sibling session. Работает и после отзыва/истечения parent, чтобы
можно было завершить старый browser login. Отзыв parent сразу отключает все зависимые
sessions при следующей проверке; ядро не заменяет независимый account recovery.

## HTTP-интеграция и оставшаяся граница

[M3b.2](browser-http.md) реализует opt-in HTTP login/bootstrap/logout по существующему
ключу. Он не подключает cookie к market/media: сначала M3b.3 session authority
в core transaction. Автоматический onboarding, recovery и форма ещё не готовы.

- Cookie `__Host-…`, Secure, HttpOnly, SameSite=Strict, Path=/, без Domain; HTTPS only.
  Не расширять trust на insecure loopback или произвольные прокси-заголовки.
- Session fixation/rotation policy, bounded same-origin login с проверенной identity,
  CSRF header для изменений/фото, no-store bootstrap/logout.
- Cookie не принимается на `/mcp` и admin; Bearer и browser credentials не смешиваются.
- Browser action map — typed fixed операции того же MarketAdapter; повторная core auth.
- Автоматический onboarding, credential loss/recovery/renewal и abuse/rate budgets
  необходимо согласовать до внешнего запуска; не подменять бессрочным master key.

## Лимиты и остаточные риски

Максимум2048 сохранённых session rows /16 на пользователя, включая revoked/expired.
Это deliberately bounded **lifetime cap**, не production UX. Отдельная reviewed
cleanup/retention policy нужна до внешнего auto-onboarding, иначе после16 входов
пользователь упрётся в лимит. Не добавлять скрытый DELETE/reset на каждом логине.

Resolve обновляет idle в SQLite write transaction: конкурентность/нагрузка/lock budgets
требуют отдельного профиля. Clock rollback до last_seen fail-closed; корректная wall
clock нужна на сервере. Восстановление старого DB может вернуть revoked sessions/keys:
общая recovery/revocation reconciliation до expose копии остаётся открытой задачей.
Один retained snapshot не доказывает безопасный disaster recovery.

Тесты — [synthetic core acceptance](../tests/test_browser_sessions.py), только Actions.
Нет реальной авторизации/ключей, HTTP routes, cookie delivery, browser screenshots,
формы, VPS или публикации в этом срезе.
