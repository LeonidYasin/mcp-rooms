# ADR-001: собственное минимальное marketplace-ядро поверх MCP Rooms

Статус: **выбрано агентом как направление ограниченного MVP в рамках поручения
продолжить работу**. Не owner-approved production ADR; пересмотр после вертикального
среза. Не подтверждает runtime acceptance или преимущество в скорости/стоимости.

## Решение

Для первого объявления продолжаем существующий Python/SQLite проект **как модульный
монолит**. HivePress/WordPress и Osclass сейчас не устанавливаем и не делаем вторую
учётную систему. Широкий поиск альтернатив закрыт; готовые продукты остаются reference
и резервом, а не обязательным фундаментом.

**Пишем свой предметный слой, переиспользуем зрелую инфраструктуру.** Не пишем MCP,
HTTP, crypto, image decoder, HTML escaping или OAuth протокол с нуля. Существующий
официальный MCP SDK и ASGI остаются; поддерживаемые шаблонизатор/библиотека изображений
выбираются и закрепляются отдельно с license/dependency review, до добавления в runtime.

## Почему это разумно именно здесь

[Исследование](../marketplace-research-final.md) и [проверка исходников](../candidate-source-checks.md)
показали реальную полезность готовых каталога, фото, кабинета и модерации, но также
несовпадения с contact-free identity и необходимость собственного credential/domain
adapter. Бесплатность core не устраняет цену интеграции и совместимости обновлений.

Наш продукт отличается не стандартной витриной, а единым действием человека/агента,
псевдонимной identity, раздельными ключами/scopes, явным согласием и отдельным admin MCP.
Существующий Rooms core уже решает часть этих задач, хотя новые listing/web/media
функции ещё отсутствуют. Для **одной контактной продажи** оставшийся domain существенно
уже полной marketplace suite. Это обоснование выбора объёма, не числовая оценка труда.

Разработка с ИИ делает собственный вариант практичнее, но не освобождает от regression,
negative ACL, dependencies, operational recovery и человеческой проверки товара.
Решение не основано на обещании «ИИ напишет без ошибок».

## Минимальные архитектурные границы

```text
Человек: browser session / CSRF ─┐
Агент: verified scoped Bearer ───┼→ общие application services → repositories → SQLite
Anonymous public GET ───────────┘          │
                                allowlisted public read model
Admin: отдельное ASGI/MCP app → admin policy → moderation/category service + audit
Media ingestion → private filesystem → validated re-encoded public derivative
```

- **Domain**: Listing/Category, transitions, validation, publication consent;
  не импортирует SQLite/HTTP/MCP и private helpers RoomStore.
- **Application**: actor/scopes/ownership, transactions, command idempotency,
  expected_revision CAS, media/category validity, admin moderation. Правила одинаковы
  для web и MCP; спрятанная кнопка не является проверкой права.
- **Persistence**: SQLite, additive migrations, repositories; transaction owner один.
  User-facing действия не держат write transaction во время декодирования изображений.
- **Adapters**: существующие rooms MCP, будущие listing MCP, browser forms/read pages,
  отдельный admin MCP. Один источник listing данных; нет независимых web/MCP карточек.
- **Media**: файлы вне SQLite; opaque IDs, ownership, decode/re-encode, EXIF stripping,
  лимиты bytes/pixels/count, staging/cleanup; публикация только проверенных derivatives.
- **Admin**: отдельная audience/credentials, без auto-signup; минимум health, категории,
  hide/restore/report audit. Не admin shell, не произвольные SQL/пути и не VPS password.

Один логический монолит **не требует одного security principal или одного endpoint**.
Публичное приложение и admin application разделяются; deployment topology/пользователи
ОС и DB privileges определяются до TEST. Общая SQLite допустима, но ограничивает
изоляцию процессов: это явно проверяемый trade-off, не обещание полной sandbox isolation.

Нынешние shared rooms не превращаются в private chat и не экспортируются в web.
Private responses — отдельная модель доступа и хранения; TTL room messages не
является сроком жизни объявления. Удаление комнаты не удаляет карточку товара.

## Первый вертикальный срез и определение «готово»

**Цель: реальное объявление б/у унитаза доступно по ссылке и принимает закрытый отклик
другого пользователя.** Продажа не гарантируется и не симулируется.

1. **Данные и права:** категории + persistent drafts + транзакционные revision/retry;
   targeted disentangling общих primitives, без большого переписывания Rooms.
2. **Фото и публикация:** безопасные фото → предпросмотр → consent конкретной версии →
   публичная карточка, поиск/категория, снятие/продано. Настоящие изображения; тексты
   о состоянии только подтверждённые продавцом. Снятие и мытьё уже подтверждены.
3. **Один предмет — два интерфейса:** browser session и listing MCP проходят один service;
   revocation и чужой write deny на обоих. Агент не получает session-cookie пользователя.
4. **Отклик и минимальная модерация:** приватный response участников, отдельный admin MCP,
   complaint/hide/restore + reason/audit. До публичного TEST нет автоматической регистрации
   без отдельно выбранных abuse limits и политики; public browsing не требует регистрации.
5. **Приёмка и изолированный TEST:** CI conformance + backup/recovery/media bounds,
   затем только одобренный operator-run VPS rollout; реальные клиенты и независимый
   покупатель. Полный [контракт приёмки](../marketplace-conformance.md).

Это пакеты работ, **не пять команд или обещание пяти коротких итераций**. Первые два
показывают локально/CI работающую карточку, но без пунктов 3–5 нет публичной готовности.
Существующие listing_contract fixtures не заменяют эти end-to-end проверки.

## Что сознательно не включаем

- Встроенную оплату/escrow/комиссии, верификацию продавца, гарантии сделки.
- Такси, диспетчеризацию, подтверждение исполнителей, tracking и delivery billing.
- Федерацию/Nostr export, полноценный Reddit, голосование и собственный рекомендатель.
- Обязательные embeddings/LLM, Elasticsearch/Redis/PostgreSQL, SPA build или microservices.
- Полный cabinet/marketing automation/moderation suite, до доказанного спроса.

Категории — минимальная иерархия, не тысячи taxonomy attributes. Сантехника первой
вещи не ограничивает продукт сантехникой, одним городом или одной страной.
Поездки/доставка остаются отдельными последующими сценариями, не «ещё один тип поста».

## Принятые риски и границы отказа

- Фото/session/abuse/moderation лежат на нас; reuse engine решил бы часть быстрее готовым
  функционалом. Не делать публичный запуск ради одной красивой страницы.
- SQLite имеет ограничение writer concurrency; capacity измерить до публичного пилота.
- Одна VPS не является disaster recovery. Снимки credentials требуют revocation
  reconciliation; off-host backup/restore остаётся production gate.
- Без контактов потеря всех ключей не даёт безопасного email recovery; не имитировать его.
- No user content execution/automatic prompt following. Правки агентов не равны согласию
  человека на новые условия или опасное действие администратора.

**Пересмотр решения:** если минимальный срез требует полноценной новой commerce suite,
базовые security/media/session gates не закрываются поддерживаемыми средствами, или
измеренное сопровождение готовой основы лучше при соблюдении всех правил — вернуться
к A/B. Не считать уже потраченный труд основанием продолжать неудачную архитектуру.
Не обещать срок/ресурсы без реализации и измерений. Не продолжать бесконечный поиск
при отсутствии такого конкретного blocker.

## Что изменено этим ADR

Только решение/план/контракт приёмки. Нет новых runtime функций, объявления, регистрации,
выдачи ключей, миграций live DB, установки кандидатов, main merge или VPS изменения.
