# F1 — сокращённый путь: MCP-first объявление и read-only web

## Решение и граница

Первый деплой можно сократить, **изменив состав результата**, а не убрав проверки.
Полный сценарий с web-формой, поиском, независимыми приватными откликами и admin MCP
сохраняется в roadmap. Но его не обязательно реализовывать до первого полезного TEST.

Ближайший ограниченный результат: допущенный владелец управляет одним объявлением
через существующие user MCP/Bearer HTTP → точный preview → отдельное явное согласие →
публикация → любой читатель открывает красивую карточку и фото по ссылке → владелец
снимает объявление. Это **не открытая площадка для регистрации**, не полноценный
marketplace и не подтверждённая продажа. Приватного чата внутри пока нет; контакт
допустим только как осознанно включённый автором публичный текст описания, не как
автоматическая выгрузка профиля/телефона/email. Реальные данные и публикация требуют
отдельного согласия. Сейчас ни сервер, ни объявление не запущены этим изменением.

## Три крупных ворот до первого изолированного VPS TEST

1. **Кандидат:** read-only карточка/фото; фиксированная opt-in composition;
   отдельный проверяемый bootstrap НОВОЙ private БД/root и least-privilege owner;
   закреплённый wheel/checksum и smoke из установленного пакета в Actions.
2. **Эксплуатационная приёмка:** один native worker/upload в малом TEST;
   ресурсные/OS filesystem+network ограничения декодера, negative fixtures;
   согласованный DB+files backup/restore с повторным применением отзыва/disable;
   reviewed retention, stop/rollback. Нельзя считать существующие два decoder slots
   с RLIMIT_AS 512 MiB каждый подходящими для VPS по старому отчёту RAM.
3. **Одобренная установка:** свежий read-only preflight с разрешением;
   отдельные пользователь/unit/БД/root/порт (не перезаписывать прежний Rooms TEST);
   loopback synthetic smoke; затем отдельно разрешённые HTTPS/external checks и
   публикация реального объявления. Не использовать старый rooms-only installer
   с SHA `4b2351c0…` как installer marketplace.

Это крупные группы, **не три команды и не обещание трёх сообщений или срока**.
Первый технический loopback может закончиться на синтетическом приватном preview;
публичная карточка требует пройденных safety gates и отдельно одобренного HTTPS.
В каждом коммите уточняются реальные blockers. Полный прежний маршрут ≈6 групп
остаётся для более широкого результата, а не объявляется наполовину выполненным.

## Что отложено, но не потеряно

- Browser editing: M3b.3 transaction-time session authority, onboarding/recovery,
  bounded retention, typed commands, форма и real-browser E2E. Cookie не используется
  для записи в сокращённом варианте: это отсутствие такой функции, не обход CSRF.
- Лента/поиск/SEO, саморегистрация marketplace, приватные отклики и admin MCP.
- Такси, вакансии, команды, инвесторы, payments и embeddings.

Admin MCP не заменён общим shell: typed операторский bootstrap — только закрытая
подготовка TEST, не публичная функция. Для малой площадки до открытого запуска нужны
средства модерации/жалоб и политика запрещённых товаров, не только красивая карточка.

## F1: контракт read-only карточки

Исходник: `src/mcp_rooms/public_web.py`; CI: `tests/test_public_web.py`.
[Exact-SHA F1 acceptance](ci-f1.md):645 tests на Python3.12. Это не deployment.
Explicit trusted composition `create_app(..., market=adapter, public_market=True)`.
Default CLI остаётся rooms-only; никаких DDL/migration/key issuance на request.

Внутренние пути после снятия proxy-prefix:

- `GET /market/{listing_uuid}` — escaped UTF-8 HTML, adaptive layout, plain text,
  категория/цена/локация/фотографии из allowlisted `PublicationStore.public_get`.
- `GET /market/{listing_uuid}/photos/{publication_epoch}/{media_uuid}.jpg` — только
  прикреплённый опубликованный derivative через `public_photo`, не blob path.

Внешний prefix строится только из проверенного resource, например `/rooms-test/mcp`
даёт `/rooms-test/market/...`. Host точный configured authority (не localhost alias).
Query запрещён; POST/HEAD/OPTIONS/прочие методы405; нет feed/JSON listing API/CORS.
GET допускает переход по внешней ссылке; этот публичный exception не применяется к
MCP/credentials/browser/private media. Cookie и Authorization не дают public GET
никаких дополнительных полномочий. Root `/market` возвращает404, не индекс.

Каждое чтение заново проверяет active publication, disabled owner, expiry, category,
manifest/bytes и повторную проверку после IO. Private/missing/withdrawn/damaged
одинаково404. Withdrawal останавливает новые чтения, но не стирает уже скачанные
копии; гонка после последней проверки и in-flight response не отменяются физически.
Нет owner UUID, credential, private room или внутренних путей в карточке.

Ответы no-store, nosniff, no-referrer, CORP same-origin, noindex; CSP default none,
локальные картинки и SHA-hashed статический CSS, без JS, unsafe-inline, remotefonts,
tracking, raw HTML участника и автоссылок. Нет фиктивного рейтинга/бейджа проверки
или неработающей кнопки чата/покупки. Публикация не означает проверку товара.

Admission: максимум2 public requests, немедленный429,120 чтений за fixed minute
на процесс, без IP-map. Слот удерживается до окончания bounded send10s. Это **не**
fleet антибот, не доказательство устойчивости к DoS и не OS resource sandbox;
thread/SQLite ожидания отдельно ограничиваются нижними слоями. Несколько процессов
умножат бюджет; TEST candidate должен быть однопроцессным. Unexpected errors503
без текста исключения. Native decoding при публичном чтении не запускается.

Publication consent notice обновлён до `live-publication-consent/v2`: preview больше
не заявляет, что public transport обязательно выключен. Старые intent digests
не должны давать новое согласие. Core поле `public_transport_enabled: null` означает
«composition неизвестна core», не включённый endpoint; availability не выводится
из preview. Старые receipt/snapshot и live migration этим изменением не тестируются
на VPS; runtime gates остаются отдельными.

## Приёмка и продолжение другим ИИ

CI использует только synthetic данные/ключи. Проверяются MCP publish → anonymous
HTML/photo → withdraw404; XSS, private/disabled/missing/bad epoch, неверный Host/query,
опт-in/default isolation, HTTP methods, cookie non-authority, budgets,503 и broken file.
Предыдущие native worker и publication race suites сохраняются. CI не заменяет
будущий screenshot/accessibility browser QA или external HTTPS/read/load acceptance.

[F2 candidate](test-candidate.md) принят как strict fresh-test composition/bootstrap/package с
одним worker и без автоматических startup migrations; не команда запуска на VPS.
Следуйте [AGENTS.md](../AGENTS.md), [work-state](work-state.json) и
[handoff](ai-handoff.md). Не продолжайте автоматически M3b.3 как blocker первого
MCP-first TEST; эта задача сохранена в paused tracks и обязательна до browser writes.


### Уточнение после F3a

[F3a OS child policy принят в CI](ci-f3a.md). До разрешённого VPS TEST остаются
два подготовительных кодовых блока: F3b DB+photos restore/current security-state и
F3c dependency/resource/operator package; затем отдельно одобренные свежий preflight,
loopback install и HTTPS/external acceptance. Это не две команды/два сообщения и
не обещание production. Проверка Landlock на нашем VPS пока не выполнялась.
