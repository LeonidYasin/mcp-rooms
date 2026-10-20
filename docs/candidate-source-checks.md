# Проверка кандидатов: готовый движок против собственного ядра

**Следующее решение:** [ADR-001](decisions/001-marketplace-foundation.md) выбирает
ограниченное собственное ядро для MVP после этой проверки. Ниже сохранены доказательства
и сравнение; прежние формулировки «кандидат ещё не выбран» относятся к стадии исследования.

Статус: source-level spike, не runtime test и не окончательный ADR.
Основание: [исследование](marketplace-research-final.md) + уточнение владельца:
готовый аналог не имеет автоматического преимущества перед чистой собственной
архитектурой. ИИ может снижать стоимость разработки и изменений; это предпосылка
для сравнения, не измеренное ускорение и не доказательство безопасности.

## Равноправные варианты

A. WordPress + HivePress + ListingHive + официальный MCP Adapter.
B. OsclassPoint + ограниченный пользовательский/admin MCP adapter.
C. Собственный небольшой marketplace domain на существующем Python/SQLite Rooms,
   с готовыми MCP SDK, ASGI, шаблонами/escaping и библиотекой обработки изображений.

C — не написание собственного протокола MCP, криптографии, HTTP-сервера или полного
аналога Авито. A/B — не бесплатная автоматическая интеграция всех наших требований.
Нет выбранного победителя по результатам только этого чтения. Предыдущий порядок
«сначала HivePress» означает порядок проверки, не обязательство выбрать его.

## Подтверждённые результаты чтения HivePress

Версия исходников: `2dfeebbaa39c10e7087fe3d5bda332b0d5aa9fc0`.

- [Модель User](https://github.com/hivepress/hivepress/blob/2dfeebbaa39c10e7087fe3d5bda332b0d5aa9fc0/includes/models/class-user.php)
  содержит email с `required => true`, alias `user_email`; сохранение использует
  WordPress `wp_insert_user`. [Форма регистрации](https://github.com/hivepress/hivepress/blob/2dfeebbaa39c10e7087fe3d5bda332b0d5aa9fc0/includes/forms/class-user-register.php)
  включает email/password. Наше enrollment без контакта не совпадает с default path.
  Hooks могут позволить адаптацию, но её полнота и влияние на plugins ещё не доказаны.
- [Listing controller](https://github.com/hivepress/hivepress/blob/2dfeebbaa39c10e7087fe3d5bda332b0d5aa9fc0/includes/controllers/class-listing.php):
  `update_listing` проверяет login и owner/status либо `edit_others_posts`; это
  положительное свидетельство существующего контроля, не отсутствие безопасности.
- `get_listings` в этом контроллере требует `edit_others_posts` и ограничивает
  поисковый запрос. Это не доказанный универсальный публичный search API для нашего
  каталога. Другие query/service пути возможны; публичный MCP поиск нужно отдельно
  проектировать. Нельзя выдавать всем агентам elevated capability ради удобства API.
- Модерация/публикация и формы встроены в жизненный цикл WordPress/HivePress;
  есть email notifications и переход в `pending`. Нельзя просто прокинуть произвольное
  поле status из MCP, минуя этот lifecycle и согласие пользователя.
- В прочитанном `update_listing` не обнаружен наш explicit expected_revision или
  client idempotency key. Это ограниченный результат чтения, не доказательство
  отсутствия любой защиты во всём WordPress. Для наших команд CAS+retry потребуют
  отдельного подтверждённого механизма, не check-then-save в двух запросах.

## WordPress MCP Adapter: что он действительно решает

Проверена документация тега `v0.7.1`:
[transport permissions](https://github.com/WordPress/mcp-adapter/blob/v0.7.1/docs/guides/transport-permissions.md),
[default/custom servers](https://github.com/WordPress/mcp-adapter/blob/v0.7.1/docs/guides/default-server.md).

- Можно объявить отдельные custom servers с фиксированными abilities; default
  discover/execute server можно отключить. Это полезно для узких user/admin входов.
- Есть transport gate и отдельные ability permissions. Но обычные WordPress
  capabilities сами по себе не наши per-credential scopes/audience/prepare-confirm.
- Документация говорит, что исключение transport permission callback приводит
  к fallback `is_user_logged_in()`. Для admin audience это требует негативной
  проверки: ошибка custom policy не должна расширять доступ обычному пользователю.
  Поведение реализации и достижимость в нашем сценарии ещё не проверены; **это не
  объявленная найденная уязвимость**. Per-ability admin checks остаются обязательными.
- Default server guide описывает session header после initialize и отсутствие GET SSE
  в описанном flow. Проверять exact client/protocol version на Qwen/Notion; нельзя
  переносить наш успешный Python SDK pilot на этот transport по одному названию MCP.
- Не копировать пример списка raw API keys в options как нашу production схему.
  Требуются digest-only credentials, revocation и проверка каждого запроса.

## Osclass: какие адаптации уже видны

[UserActions.php](https://github.com/osclass-classifieds/osclass/blob/34bd39ecb88e6be95b091803ff25170174ae7615/oc-includes/osclass/UserActions.php)
на зафиксированном ref:

- `add()` проверяет password, name, валидный email и занятость email.
- При активации user привязываются существующие items по `s_contact_email`, alerts
  и reports. Email здесь не только скрываемое поле формы, но связь workflow.
- Поэтому no-email UUID enrollment требует проверки всей цепочки identity/ownership,
  а не фиктивного общего email или назначения всех объявлений одному service account.
  Отсутствие email verification не равняется отсутствию обязательного email.

Официальный [REST API plugin](https://osclasspoint.com/osclass-plugins/seo-speed-admin/rest-api-osclass-plugin-i114)
на момент просмотра — платный продукт. Описывает 60+ операций, API keys с read/insert/
update/delete и примеры key в query URL. Это не обязательная покупка и не доказательство,
что свободный собственный adapter невозможен. Но paid plugin нельзя считать бесплатным
готовым API, а operation scope нельзя считать проверкой owner каждого объекта.
Raw token в URL для нашего клиента не допускается. Не исследованы internals этого
платного плагина; не объявлять его небезопасным только по примеру документации.

## Наш собственный код: преимущества и недостатки без идеализации

Прочитаны `listing_contract.py`, `service.py`, импорты/границы `server.py`, `store.py`,
`identity.py`, `admin.py` существующей ветки проекта. Никакого кода не запускалось.

**Уже полезно:** стабильный UUID owner, digest credentials/revocation/scopes,
проверенный ранее обмен комнат, один SQLite operational contour, официальный MCP SDK,
service layer над verified principal. Не нужно синхронизировать WordPress и Rooms users.

**Не готово:** persistent listings, atomic revision CAS, media service, safe web sessions,
публичные страницы/search, private response, category hierarchy, moderation/admin MCP.
Ранее пройденные Rooms tests не доказывают безопасность этих будущих функций.

**Архитектурные долги:**

1. Listing contract импортирует `Principal` из identity, `RoomError`, `_id`, `_text`
   из room store. Domain связан с инфраструктурным модулем и private helpers.
2. RoomStore создаёт также таблицы users/credentials/enrollments. Удобный один snapshot
   не означает, что room repository должен владеть всеми schema responsibilities.
3. Admin сейчас — операторский CLI, не реализованный отдельный admin MCP.
4. CAS в pure contract — намерение, а не атомарное сохранение. Его нельзя маркировать
   готовым конкурентным update. Медиа IDs также не подтверждают ownership/безопасность.

Если выбираем C: вынести минимальные общие value validation/errors/principal contracts,
не разводить глобальный service locator. Совместимость Rooms сохранить fixture tests;
аддитивные миграции и общий transaction boundary. Не делать масштабный рефакторинг
работающих комнат ради красивых папок. Один SQLite файл допустим; разные репозитории
и обязанности не требуют разных DB/микросервисов.

## Сравнение оставшейся работы (качественно, без выдуманных баллов/сроков)

| Критерий | A: HivePress | B: Osclass | C: свой минимальный domain |
| --- | --- | --- | --- |
| Каталог/кабинет/админ web | Большая часть уже есть | Большая часть уже есть | Нужно написать ограниченный набор |
| Identity без контактов | Несовпадение default модели, интеграция не доказана | Несовпадение + email-linked workflow | Соответствует текущему core; web login/recovery ещё нужны |
| User/admin MCP | SDK adapter готов; domain/credential policy свои | Нужен adapter, бесплатный полный путь не доказан | SDK уже есть; listing/admin tools ещё нужны |
| CAS/idempotency/consent | Нужны проверка и интеграция с native writes | Не подтверждены | Можно явно спроектировать, но ещё не реализовано |
| Эксплуатация | WP/PHP/SQL + Rooms и согласованность identity | PHP/SQL + Rooms и identity | Python/SQLite; фактическая capacity ещё не измерена |
| Обновления | Upstream исправляет core, но совместимость plugin glue наша | Аналогично, hooks/plugin совместимость наша | Меньше внешнего домена, весь domain security/maintenance наш |
| Свобода архитектуры | Ограничена workflow/hooks движка | Ограничена workflow движка | Выше, но нет автоматической чистоты |

## Граница решения и следующий проверяемый результат

При текущих обязательных no-contact identity + MCP-first требованиях C — серьёзный
кандидат, а не запасной вариант. Пока нельзя честно объявить его быстрее/дешевле A/B.
Готовность фото/модерации/кабинета у готовых движков — значимое преимущество, которое
не отменяется одной найденной несовместимостью регистрации.

Следующая стадия — общий conformance contract для A/B/C: draft/photo/preview/consent,
public read, чужой write deny, revoked credential deny, concurrent edit conflict,
duplicate retry, private reply isolation, admin fail-closed, backup/restore. Тесты не
должны знать WP post IDs или внутренние таблицы Rooms. Затем минимальный vertical slice
каждого реально оставшегося финалиста на одинаковых требованиях, а не три полных рынка.
Runtime только GitHub CI или отдельно разрешённая изолированная среда; VPS не трогать.

Критерий остановки адаптации: обязательное правило возможно только через общий admin
service account, правку vendor core, вторую writable копию каталога, раскрытие контактов
или обход auth. Тогда отказаться от такого способа интеграции, не замалчивать цену.
Если поддерживаемые hooks решают правило без этого — считать кандидата жизнеспособным.

Окончательный ADR должен выбрать основу по оставшейся проверенной работе и сопровождению,
не по лозунгу «не изобретать велосипед» или «ИИ всё напишет». Пока новые реализации,
установка кандидатов, merge/main и production не выполнялись.
