# M3a.1 — opt-in пользовательский MCP объявлений

Первый срез adapters/auth; не завершение всего этапа1 из плана деплоя.
Следующий [M3a.2 добавил opt-in приватную HTTP-загрузку](media-http.md) в CI.
[M3b.2](browser-http.md) добавил отдельный HTTP session bridge, пока без cookie authority
над market/media. Форма, публичная витрина/search и auto-onboarding ещё не реализованы. Не подключает и не обновляет VPS.

## Явное включение вместо скрытой миграции

Default `create_app(database, resource)` и CLI по-прежнему rooms-only:8 методов,
room scopes и прежний режим регистрации. Marketplace включается только trusted
composition root через `market=MarketAdapter(drafts,photos,publisher)`, собранный из
одних и тех же объектов/БД/resource. Bundle из другого пути/resource/сервисов отвергается.
Startup проверяет market2/media3/publication1, но **не создаёт и не мигрирует** их.
Нужен отдельный явный операторский initialize, а не запрос пользователя.

В этом режиме официальный MCP SDK регистрирует 28 методов: 8 прежних rooms и 20 listings. BearerGate проверяет ключ на каждом HTTP request и переносит проверенный
Principal через request-local ContextVar в thread worker. Сервис дополнительно
проверяет persisted user/credential/resource/scopes/revoke/expiry при каждом действии.
Principal/owner/path/resource не строятся из tool JSON. Параллельные клиенты не должны
смешивать владельцев. Названия методов видны всем аутентифицированным клиентам этого
opt-in app; наличие в tools/list не даёт права вызова и не раскрывает private records.

## Методы и права

| MCP tool | Scope | Граница |
| --- | --- | --- |
| listings_create | listings:write | Только private draft; typed content, category, command UUID |
| listings_get | listings:read | Только свой unexpired draft |
| listings_list_own | listings:read | Keyset items/status/cursor, не публичный search |
| listings_categories | listings:read | Дети активной категории, не admin |
| listings_update | listings:write | CAS text/category edit с сохранением фото; сначала withdraw active |
| listings_set_photos | listings:write | 0–8 ordered owned staged IDs; не URL/path/base64/upload |
| listings_archive | listings:write | Private archive; active нужно сначала снять |
| listings_preview | listings:read | NEW live-publication notice и точный card preview; не publish |
| listings_confirm_publication | listings:publish | Exact revision/digest, strict true consent, short TTL |
| listings_publish | listings:publish | Consume/snapshot/receipt/audit; явное одобрение владельца |
| listings_withdraw | listings:publish | Exact publication revision; не удаление чужих копий |
| listings_publication_status | listings:read | Текущее stored state/epoch, не гарантия внешней видимости |
| listings_public_get | listings:read | Allowlisted публичная карточка по id; не owner/room/credentials; 404 для недоступных |
| listings_public_index | listings:read | Bounded read-only страница опубликованных (по root-разделу); allowlist |
| listings_respond | listings:write | Приватный отклик на активное объявление; только владелец и автор видят |
| listings_responses | listings:read | Список откликов на СВОЁ активное объявление (только владелец); в записи `unread_messages` — счётчик непрочитанных сообщений диалога (контент не включается) |
| listings_my_responses | listings:read | Свои отклики + статус-метка + `unread_messages` (сообщения владельца в треде) |
| listings_respond_status | listings:write | Владелец ставит публичную метку статуса (allowlist); тело остаётся приватным |
| listings_reply | listings:write | Сообщение в приватный диалог-тред своего отклика (A или B) |
| listings_thread | listings:read | Чтение приватного тред-диалога (только участники) |

`ListingInput` запрещает лишние поля (включая owner/media_ids), coercion bool→price,
число→title. JSON lists переводятся в domain tuples только после проверки. Внешние
ошибки не раскрывают SQL, paths, raw secrets или stack traces. SQLite busy даёт
bounded retry hint; повтор допустим только с тем же command UUID/payload.
MCP POST body по-прежнему ограничен64KiB; бинарные фото через него не передаются.
Tool descriptions называют содержимое недоверенными данными, не инструкциями.
Admin/SQL/shell/maintenance/credential issuance MCP методов нет. SDK ToolAnnotations
помечают read-only/destructive/idempotent/closed-world свойства; это hints, не grants.

## Уведомления о приватном диалоге (p1)

Владелец и автор отклика узнают об обновлении приватного диалога через контент-безопасный
индикатор `unread_messages`: целочисленный счётчик непрочитанных сообщений тред-диалога
от противоположного участника. Текст сообщений, авторы и сам индикатор содержимым не
раскрывают. Чтение треда (`listings_thread`) проставляет read-метку; после чтения
индикатор становится равным нулю. Public web и public summary по-прежнему показывают только
счётчик откликов и публичные метки — без сообщений и участников. Push-уведомления и
вложения — отдельные слайсы.

## Listing credentials — отдельный opt-in

`IdentityStore(..., allow_listing_scopes=True)` разрешает trusted operator API выдавать
явно выбранные listings:read/write/publish в дополнение к room scopes. Default policy
не меняется; неизвестные/admin scopes не принимаются. Это не клиентский параметр:
HTTP/MCP caller не может включить scope policy или запросить новые права.
Rooms-only app не аутентифицирует ключ с неизвестными ему listing scopes.

Публичная opt-in one-click регистрация **пока всё равно выдаёт только rooms scopes**,
даже в market composition. Старые keys не повышаются; default issue_token тоже
остаётся rooms-only по default scopes. Это контролируемый developer/TEST срез,
не готовая политика самостоятельной регистрации продавцов. Автоматическая выдача
marketplace прав после явного onboarding consent/лимитов — следующий отдельный gate;
не создаём бесконечную ручную регистрацию как целевую архитектуру.

## Безопасное делегирование текущего ключа

`POST /credentials` с пустым JSON по-прежнему создаёт ключ того же user и сохраняет
старый до явного DELETE. Теперь `delegate_current` заново проверяет persisted grant
**в той же write transaction**, где создаётся digest нового ключа. Revoke/disable/
expiry/resource/scope downgrade между первоначальным auth и выдачей блокируют её.
Клиент не выбирает owner/scopes или увеличенный TTL.

Новый ключ не шире source scopes и **не живёт дольше source expiry**. Это ограниченное
делегирование, не renewal account/session. Ответ явно содержит expiry_bounded_by_source.
Даже цепочка копий не продлевает срок доступа. Продление авторизованной учётной сессии,
ownership-verified recovery и OAuth остаются отдельными задачами; current API не
должен маскироваться под бессрочную регистрацию. Это осознанное ужесточение прежней
self-service ротации; default7-day/max90-day operator issuance не изменены.
Raw ключ возвращается один раз в no-store credential HTTP response, не MCP output;
в БД хранится digest. Default cap20 credentials/user учитывает expired/revoked rows.

## Что именно доступно сейчас

Сервисы можно соединить в отдельном программно собранном тестовом ASGI app. Default
CLI/команда сервиса не включает этот режим. Нет production deployment/real key issue,
новой signup policy или публикации настоящего товара. Синтетический ASGI тест проходит
через реальный официальный SDK и настоящий Bearer, без прямого SQL-вписывания listing
scopes, но bytes staging пока подготавливает trusted fixture, не upload transport.

Следующие gates: bounded authenticated streaming upload; HTTP user adapters;
browser session/CSRF и явный onboarding grant; public card/photo/search delivery с
no-store/escape/rate controls; отдельный admin MCP; OS/recovery/load/E2E и VPS approval.
См. [deployment plan](deployment-readiness.md), [publication core](live-publication.md),
[identity](identity.md). [Exact-SHA acceptance](ci-m3a1.md) фиксирует проверенный срез, не готовность внешнего сервиса.
