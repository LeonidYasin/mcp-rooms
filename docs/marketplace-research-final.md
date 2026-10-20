# Готовые основы для MCP Rooms Market: итог исследования

## Статус и границы результата

Исследование GitHub, официальных сайтов, README, лицензий и отдельных исходников
достаточно завершено **для выбора короткого списка**, не для production approval.
Это desk research: конкуренты не установлены, их тесты/нагрузка/безопасность не
проверены исполнением. Не гарантируется нахождение всех существующих проектов.
Проверены независимые классы решений: classifieds, commerce, сообщества, комнаты
агентов, MCP/A2A, децентрализованные рынки, транспорт/доставка. Дальнейший широкий
поиск уступает по пользе ограниченной проверке двух финалистов.

Репозиторий публичный; этот отчёт не содержит ключей, контактов, точных адресов или
снимков БД. Реальный первый товар — **б/у унитаз, снят и помыт**. Это не означает
дезинфекцию, исправность, отсутствие дефектов или готовую публикацию.

## Вывод

**Не писать полный аналог Авито с нуля до проверки готового движка.**

1. Первый кандидат для технической проверки: **WordPress + HivePress + бесплатная
   ListingHive + официальный WordPress MCP Adapter**. Готовые каталог, категории,
   веб-интерфейс и администрирование; официальный адаптер закрывает протокол MCP,
   но не реализует наши предметные операции и права автоматически.
2. Резервный кандидат: **OsclassPoint / osclass-classifieds/osclass, Apache-2.0**.
   Это специализированный classifieds, а не только старый заброшенный Osclass.
   Потребуется проверить/сделать безопасный пользовательский и admin MCP адаптер.
3. **Shopstr** — наиболее близкий обнаруженный готовый рынок с собственным MCP.
   Однако его проверенный MCP-пакет только читает каталог; это не готовая замена
   публикации, личным переговорам и административному входу нашего проекта.
4. Сохранить самостоятельный MIT Rooms core и проверенный обмен Qwen/Notion.
   Если объявления принадлежат внешнему движку, он — единственный источник истины;
   не создавать вторую изменяемую копию каталога в Rooms SQLite.

Это рекомендация для spike, **не принятое решение перейти на PHP/MySQL**, не план
немедленно установить все движки. Текущая реализация Python/SQLite остаётся как есть.
Если обязательные identity/security требования потребуют масштабной переделки готовой
основы, сравнить этот объём с минимальным собственным listing service, а не с полным
самописным marketplace. Не считать ни один путь заранее дешевле без проверки.

## Критерии, связанные с нашим продуктом

- Бесплатное используемое ядро и понятная лицензия, не ограниченный SaaS trial.
- Настоящие фото, категории/атрибуты, цена, приблизительная локация, поиск, stable URL.
- Draft → preview → явная публикация, снятие/продано, модерирование и жалобы.
- Пользование человеком через web и агентом через MCP одной записью и правилами.
- Доступ не ограничен населённым пунктом; город — фильтр, а не условие регистрации.
- Нет обязательного GitHub, телефона, email или публичного профиля для участия.
- Раздельные identity/credentials, owner checks, scopes, revocation, безопасная web session.
- Отдельный admin MCP: аутентификация/полномочия/allowlist/audit/подтверждение риска.
- Приватный отклик не является нынешней общей комнатой с TTL 24h.
- Возможность обычного объявления без Bitcoin, escrow, платного LLM или embeddings.

## Короткий список: что готово и что не доказано

| Основа | Бесплатность и лицензия | Подтверждено документацией/исходниками | Основной пробел для нас |
| --- | --- | --- | --- |
| HivePress + ListingHive | Бесплатные plugin/core и тема, GPL-3.0; дополнительные расширения бывают платными | Listings, категории/поля/поиск, moderation, accounts, hooks и заявленный REST API; готовая тема | Проверить конкретные бесплатные messaging/фото-возможности и API ownership; UUID/no-email identity не доказана |
| WordPress MCP Adapter | Официальный пакет, GPL-2.0-or-later | HTTP/STDIO, несколько серверов, per-server auth, per-ability permission checks | Нужны наши зарегистрированные abilities для HivePress, права, scopes и разделение admin/user; наличие адаптера не создаёт marketplace API |
| OsclassPoint Osclass | Apache-2.0, self-hosted; темы/плагины могут иметь иные условия | Photos/listings, дерево категорий и locations, search, custom fields, admin/moderation; release 8.4.0 | Не доказан готовый actor-scoped MCP/REST для всех операций; отдельный PHP/SQL стек |
| ShopClass (Mindstellar) | GPL-3.0-or-later, отдельное наследие Apache | Продолжение Osclass; категории, атрибуты, фото, accounts, modern admin, hooks | Другой вариант, не смешивать с Apache OsclassPoint; наш MCP/auth не доказан |
| Shopstr | GPL-3.0; открытый Nostr marketplace | Web marketplace + реальный read-only MCP, поиск/карточки/категории/репутация | Проверенный MCP — STDIO и только чтение, нет seller write/admin; Nostr signing/relays и Bitcoin-oriented UX отличаются от наших требований |

### Почему WordPress-связка — только кандидат, а не готовая интеграция

[HivePress README](https://github.com/hivepress/hivepress/blob/2dfeebbaa39c10e7087fe3d5bda332b0d5aa9fc0/README.md)
описывает REST/hooks, каталог, поля и поиск. [ListingHive](https://github.com/hivepress/listinghive)
— бесплатная тема. [Marketplace extension](https://hivepress.io/extensions/marketplace/)
для транзакций/комиссий — платный дополнительный компонент; он не нужен для первой
продажи с согласованием вне платформенной оплаты. Состав бесплатных расширений
проверять по [официальному каталогу](https://hivepress.io/extensions/), не по рекламе
«all-in-one». Бесплатность core не доказывает бесплатность любой желаемой функции.

[Официальный MCP Adapter](https://github.com/WordPress/mcp-adapter) мостит Abilities
API в MCP. Документация подтверждает несколько серверов и отдельные проверки доступа.
Abilities по умолчанию не выставляются; opt-in `meta.public` / `meta.mcp.public`
означает экспозицию способности, **не разрешение анонимно выполнять её**.
[Abilities API](https://developer.wordpress.org/apis/abilities-api/) относится к
WordPress 6.9+. Для каждой нашей ability обязательна проверка actor/capability/owner;
не выставлять все операции WordPress или произвольное исполнение кода/SQL.

Отдельно проверить, можно ли сохранить простую псевдонимную регистрацию без email,
как связать стабильного пользователя Rooms с WordPress account, выдавать разные
отзываемые ключи агентам и входить через безопасную браузерную session. Это не решено
наличием Application Passwords или примера подключения MCP. Если не получается без
небезопасных обходов, кандидат не проходит.

### Osclass: исправление прежнего вывода

Текущий [OsclassPoint репозиторий](https://github.com/osclass-classifieds/osclass/blob/34bd39ecb88e6be95b091803ff25170174ae7615/README.md)
и [Apache LICENSE](https://github.com/osclass-classifieds/osclass/blob/34bd39ecb88e6be95b091803ff25170174ae7615/LICENSE)
проверены отдельно от исторического `osclass/Osclass`.
[Release 8.4.0](https://github.com/osclass-classifieds/Osclass/releases/tag/v8.4.0)
опубликован 2026-10-02; это свидетельство текущего релиза, не аудит безопасности.
PHP/MySQL/MariaDB — не наша SQLite. Не переносить устаревшие требования PHP из
исторических README без сверки с выбранным релизом.

[Mindstellar ShopClass](https://github.com/mindstellar/shopclass) — отдельная GPL-ветвь
своей истории Osclass. Нельзя смешивать её лицензию и возможности с Apache-версией.

### Shopstr: реальный MCP, но не весь наш сценарий

Прочитаны [MCP README](https://github.com/shopstr-eng/shopstr/blob/de6040b7618cd3792e33705ac9462efd8d3c47d0/packages/shopstr-mcp/README.md),
[package.json](https://github.com/shopstr-eng/shopstr/blob/de6040b7618cd3792e33705ac9462efd8d3c47d0/packages/shopstr-mcp/package.json)
и [регистрация tools](https://github.com/shopstr-eng/shopstr/blob/de6040b7618cd3792e33705ac9462efd8d3c47d0/packages/shopstr-mcp/src/tools/index.ts).
Семь методов: `search_products`, `get_product_details`, `get_reviews`, `list_companies`,
`get_company_details`, `get_seller_reputation`, `get_categories`. MCP пакет 0.1.0,
Node >=22.4, STDIO. Read-only модель прямо исключает приватные ключи, подпись событий,
создание заказов, кошельки и checkout. Наличие web-функций не означает их доступность
через эти MCP tools или наличие remote HTTPS multi-user входа.

[NIP-99](https://github.com/nostr-protocol/nips/blob/master/99.md) полезен как формат
объявления: title/summary/images/location/category/price/status. Валюты допускают fiat,
сам Nostr не обязывает к Bitcoin. Но Shopstr продукт ориентирован на Bitcoin-commerce.
Nostr signing keys — не наши Bearer UUID-users; внешняя публикация требует отдельного
согласия, модели identity и privacy. Relay search best-effort не гарантирует полный
каталог сети. Draft event на публичном relay не обеспечивает конфиденциальность.

## Остальные исследованные направления

| Проект / класс | Что переиспользовать или учесть | Почему не основа первой продажи |
| --- | --- | --- |
| [OpenClassify](https://github.com/openclassify/openclassify) | Очень близкие модули Listing/Category/Location/Conversation/Offer/Report/Admin | Laravel/Filament/PHP/PostgreSQL другой стек. На проверенном HEAD license_spdx отсутствует, LICENSE.md не найден; MIT в composer.json — метаданные Laravel skeleton, не достаточное подтверждение лицензии всего проекта. Лицензионный gate открыт, не выбирать для копирования/деплоя |
| [Discourse](https://github.com/discourse/discourse) | Темы, чат, модерация, сообщества, REST, GPL-2.0-or-later | Полноценный форум, не готовые classifieds/сделки; Rails/PostgreSQL/Redis — дополнительная эксплуатация |
| [NodeBB](https://github.com/NodeBB/NodeBB) | Категории, realtime, плагины, REST read/write, GPL-3.0 | Форум, готовый безопасный marketplace-плагин для нашего сценария не подтверждён |
| [Lemmy](https://github.com/LemmyNet/lemmy) | Reddit-like сообщества/посты/комментарии/голосование, федерация, AGPL-3.0 | Не модель объявлений/заказов; федерация не решает наши consent/identity/admin автоматически |
| [Matrix](https://spec.matrix.org/latest/client-server-api/) | Стандарт комнат, сообщений, history и client-server auth | Протокол общения, не объявления, категории и moderation marketplace. Выбор реализации/лицензии отдельный |
| [agentchattr](https://github.com/bcurts/agentchattr) | MIT, web UI, каналы/thread replies, MCP для агентов, FastAPI/WebSocket | Спроектирован для localhost; @mention может внедрять prompts/запускать агентные действия. Это не безопасность публичного рынка, нельзя переносить auto-execution |
| [MCP Agent Mail Python](https://github.com/Dicklesworthstone/mcp_agent_mail) | Mailbox/Git+SQLite и coordination coding agents | README сообщает о прекращении поддержки и Rust successor; не рынок |
| [MCP Agent Mail Rust](https://github.com/Dicklesworthstone/mcp_agent_mail_rust) | Концепции inbox/coordination/web display | LICENSE содержит OpenAI/Anthropic Rider: не plain MIT, ограничения на стороны/использование; не переносить в наш MIT core под видом permissive dependency |
| [A2A](https://github.com/a2aproject/A2A) | Apache-2.0, Agent Cards/discovery/tasks; дополняет MCP | Протокол делегирования, не готовые web-карточки, проверенные исполнители или рынок |
| [Vendure](https://github.com/vendurehq/vendure) | GPL-3.0 commerce core, GraphQL, каталог/заказы | E-commerce backend; C2C onboarding/модерация/частные переговоры требуют интеграции, лишний контур для одного контактного объявления |
| [Medusa](https://github.com/medusajs/medusa) | Модульный commerce, MIT core | Enterprise materials отдельно лицензируются; не готовый C2C+Rooms+admin MCP |
| [Sharetribe Go](https://github.com/sharetribe/sharetribe) | Готовые marketplace-сценарии | README: no longer actively maintained; Community Public License/source-available, не plain MIT; не путать с новым hosted SaaS |
| [Cocorico](https://github.com/Cocolabs-sas/cocorico) | MIT, services/rental marketplace | Legacy stack, текущая пригодность/обновления не доказаны; rental не первая продажа вещи |
| [Yclas](https://yclas.com/pricing.html) | Развитая commercial classifieds платформа | Текущий cloud — trial/платные планы, не постоянно бесплатный сервис; старый открытый код не доказывает бесплатность текущего продукта |
| [LibreTaxi](https://github.com/ro31337/libretaxi) | AGPL-3.0, ride matching, Telegram | Текущий v2 — Go/PostgreSQL/RabbitMQ proof-of-concept, не прежний JS/Firebase и не готовый Uber; пригодится исследованию поездок позже |
| [Fleetbase](https://github.com/fleetbase/fleetbase) / [FleetOps](https://github.com/fleetbase/fleetops) | Fleet/order/dispatch, AGPL-3.0 self-hosted | Отдельный логистический стек; commercial licensing для соответствующих закрытых сценариев, cloud trial не free forever; не блокирует classifieds MVP |

Указанные возможности — заявления/контракты изученных источников, не наши выполненные
испытания. GPL/AGPL не означают запрета коммерции; обязанности зависят от интеграции,
изменений и распространения/сетевого использования. Это не юридическое заключение.
Официальные условия [Fleetbase](https://fleetbase.io/docs/community/licensing)
проверять для конкретной схемы. Исходники с неизвестными или нестандартными лицензиями
не включать в наш MIT core, не перелицензировать чужой код заголовком MIT.

## Бесплатность без самообмана

- Free/open-source software не даёт бесплатный сервер, домен, email/SMS, резервные копии.
- Уже оплаченный VPS может не требовать нового тарифа, но ёмкость PHP/SQL/Rooms вместе
  ещё не измерена. Не обещать отсутствие дополнительных расходов или SLA free tier.
- Не нужны платные Marketplace checkout, embeddings, карты и LLM для первого объявления.
- Платные LLM/embedding API позже подключаются через provider-independent adapter;
  core publish/search/read не должен зависеть от оплаты inference.
- Готовый admin web не равен готовому безопасному admin MCP.

## Следующая ограниченная проверка вместо нового бесконечного поиска

Сначала один кандидат HivePress/ListingHive/official MCP Adapter. Только source/config
review и затем отдельно согласованный изолированный тест, не установка на боевой VPS.
Если жёсткий blocker — один резервный Osclass. Не разворачивать все проекты сразу.

Обязательная последовательность приёмки:

1. Зафиксировать версии, licenses/transitive plugins и перечень действительно бесплатных
   функций; не обходить платные лицензии. Проверить minimum requirements/обновления.
2. Псевдонимная регистрация без обязательного email/телефона/GitHub; два разных владельца,
   два credentials одного владельца, revoke и ownership после ротации. Нет token в URL.
3. Draft + настоящие фото с validation/re-encode/EXIF stripping/quota; preview до consent.
4. Явный publish создаёт stable public URL; web и MCP видят одну запись. Чужие update,
   media access и delete запрещены. Конкурентные update конфликтуют, retry не дублирует.
5. Public allowlist projection без ключей/внутренних ID credentials/контактов/точного адреса;
   XSS/CSRF/session/security headers и непубличный draft тестируются отдельно.
6. Search/category/location и действительная информация о комплектности/дефектах; агент
   не генерирует факты и не выполняет команды из текста объявления/чата.
7. Приватный отклик покупателя продавцу: посторонний не читает переписку; наши старые
   комнаты не импортируются и не становятся публичными из-за добавления web.
8. Раздельный admin MCP server/audience/credentials, обязательные permission checks,
   минимальный typed allowlist, moderation/report/audit, prepare-confirm для опасных
   изменений. Никакого shell, произвольного SQL или плагина «выполни любой PHP».
9. Snapshot/restore/revocation reconciliation/rollback без изменения действующих сервисов;
   измерить память/диск/backup стоимость. Нужна явная владельческая санкция для VPS.
10. Сравнить перечень реально оставшихся работ с Python/SQLite направлением и записать
    ADR: выбранный backend, identity mapping, данные/права, стоимость эксплуатации,
    лицензии и критерии отката. После одобрения — реализация, не до проверки.

Исследование достаточно полно для этого выбора. Финальный выбор архитектуры зависит
от испытания обязательных требований, а не числа звёзд, папки `.ai/mcp` или обещания README.
Публикация реального объявления, отклик и продажа — три разных результата; ни один
не достигнут этим отчётом. Для продажи не требуется сначала строить такси/рекомендации.

## Зафиксированные исходные версии

- HivePress: `2dfeebbaa39c10e7087fe3d5bda332b0d5aa9fc0`; README + GPL license.txt.
- OsclassPoint: `34bd39ecb88e6be95b091803ff25170174ae7615`; README + Apache LICENSE;
  отдельно проверен release v8.4.0 (2026-10-02).
- Shopstr: `de6040b7618cd3792e33705ac9462efd8d3c47d0`; README/MCP README/package/tools.
- OpenClassify: `42516cfcc16659e485183905b12e99efacfad2c0`; README/composer.json,
  LICENSE.md не найден на этом ref; нельзя заменять отсутствие старым snippet поиска.
- MCP Agent Mail Rust: `88e6e77e97bf73573b541690cf631483bbfeee11`;
  [нестандартная лицензия](https://github.com/Dicklesworthstone/mcp_agent_mail_rust/blob/88e6e77e97bf73573b541690cf631483bbfeee11/LICENSE).
- Наш glacier: `f8a53422c1d21728b1671dbabc449f941318f1fd`; принцип единого web/MCP state,
  подробности в [предыдущем исследовании](reuse-marketplace-research.md).

Остальные ссылки — просмотренная документация текущих веток/сайтов, не закреплённый
supply-chain manifest. Перед установкой нужен новый version/license/dependency review.
