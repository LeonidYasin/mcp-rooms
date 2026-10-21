# До деплоя: ограниченный TEST, пилот и production

Оценка по фактическим границам проекта, не обещание календарного срока или числа
команд. Один этап может потребовать нескольких небольших коммитов/прогонов CI.
Зелёные unit-тесты не означают готовность внешнего сервера.

Цель ближайшего выпуска фиксируем: **одна настоящая вещь → фото/черновик →
подтверждённая публикация → независимый приватный отклик**. Не добавляем такси,
вакансии, инвесторов, платежи или embeddings до этого результата. География —
фильтр, не запрет регистрации людям из других мест. Технический товар — снятый и
помытый б/у унитаз, без выдуманных фото, цены, исправности, покупателя или продажи.

## Можно ли сократить путь — да, через меньший результат

[Owner-first TEST / F1](owner-first-test.md): MCP/HTTP управление одним объявлением,
публичная read-only карточка и фото по ссылке, без web-редактирования/поиска/
саморегистрации/встроенных откликов/admin MCP. Ориентир **3 крупных ворот**:
кандидат+bootstrap+артефакт; OS/лимиты/DB+files restore/rollback; разрешённый
изолированный deploy и отдельно HTTPS-приёмка. Ворота1 реализуются частями; новый
read-only transport не означает готовый installer. [F2 candidate](test-candidate.md)
выделяет fresh bootstrap/strict startup/пакетную CI-проверку; F3a child policy и
F3b offline recovery приняты в CI, F3c operator/resource package ещё blocker. Не три команды/сообщения.

Это сокращённый технически полезный пилот, а не выполнение полного сценария ниже.
Browser M3b.3 отложен только пока **вообще нет cookie-auth market writes**.
Безопасность/согласие/ACL/ресурсы/восстановление не исключаются из приёмки.

## Какой именно деплой

### Только технический loopback TEST

При желании более ранний изолированный тест декодера/хранилища возможен примерно
за **3 крупных этапа**: закреплённый устанавливаемый кандидат/config/smoke; проверка
OS isolation/лимитов/rollback; разрешённый владельцем preflight и отдельный loopback
unit с синтетическими данными. Это **не** сайт объявлений, не публикация и не
проверенный внешний пользовательский сценарий. Без работающего адаптера нельзя
называть установку пакета тестом всего marketplace.

### Внешний TEST с первым полезным сценарием

После [M2c.2 publication core](live-publication.md) ориентир — **6 крупных этапов,
включая сам TEST-деплой**. Из прежних 7 завершено транзакционное ядро публикации:
new-schema consent, consume/snapshot/receipt/audit, withdrawal и проверяемая public
projection. Это internal CI, а не публичный web или завершённая интеграционная приёмка.
Один этап может включать несколько коммитов/прогонов; найденные blockers меняют оценку,
а не отменяют security gates.

| № | Оставшийся этап | Проверяемый результат |
| --- | --- | --- |
| 1 | Общие пользовательские adapters/auth | User MCP и HTTP над одними сервисами; bounded streaming upload, least-privilege issuance, revoke/expiry, browser session/CSRF/rate limits. |
| 2 | Рабочий web | Лента/категории/карточка, реальные фото, мобильная форма, точный card preview и явное подтверждение. Не нынешний статический макет/сайт документации. |
| 3 | Приватные отклики | Два независимых пользователя, участники/ACL, нет утечки переписки в общие rooms или публичную карточку. |
| 4 | Отдельный admin MCP | Отдельные audience/ключи/scopes, typed moderation/hide/disable/complaints/audit. Никакого shell, произвольного Python или SQL. |
| 5 | Приёмка и пакет эксплуатации | E2E/negative/abuse CI, OS sandbox и адекватные VPS лимиты, DB+files restore и revocation reconciliation, квоты/retention, закреплённый артефакт и checksum/operator install+rollback. |
| 6 | Одобренный изолированный TEST-деплой | Свежий preflight; отдельный пользователь/unit/БД/root/порт; loopback smoke; HTTPS только после проверки; реальное чтение/публикация/отклик с явным согласием владельца. |

В этапе1 приняты [opt-in user MCP/auth](ci-m3a1.md), [private binary HTTP фото](ci-m3a2.md)
и [ядро browser sessions](ci-m3b1.md) с [HTTP bridge](ci-m3b2.md). Cookie пока не
подключена к market/media: M3b.3 должен проверять session внутри core transaction.
Автоматический onboarding, renewal/recovery, typed browser actions, реальный browser QA
и anti-abuse/retention остаются. Целиком этап1 не закрыт.

Этапы 1–4 — ещё не реализованные полностью пакеты, а не галочки по наличию SPEC.
Шаг 5 включает интеграцию; не выдаём успешные unit-тесты publisher за рабочий сайт.
По мере появления исходников тесты/документы обновляются вместе с ними.
Источники статусов: [карта компонентов](project-map.md), [ROADMAP](../ROADMAP.md),
[канонический план](delivery-plan.md), exact-SHA CI evidence.

## До production

Публичного production MCP Rooms пока нет. После внешнего TEST ожидаются ещё примерно
**2–4 приёмочных этапа**, а не автоматическое переключение: реальный пилот/обратная
связь и исправления; проверка нагрузки/антиспама/модерации и эксплуатационных процедур;
резервирование/восстановление и правила приватности/запрещённых объявлений; явное
решение владельца о release/main/production rollout с rollback. Точный список и
срок можно утвердить только по результатам TEST; зелёный pytest не заменяет его.

## Разрешения и отсутствие скрытого запуска

Сейчас VPS и production не изменяются. Любая серверная операция — отдельное явное
разрешение владельца; remote run_python/обход через shell/SSH не используются без
его специального подтверждения/пароля. Подготовить проверяемый скрипт для ручного
запуска — не то же самое, что выполнить его. main/merge/release также отдельно.

GitHub Pages — версионируемая документация, а не marketplace. Сохраняется отдельный
[single-publisher Pages gate](ci-pages.md#remaining-single-publisher-configuration-gate):
дублирующий branch/Jekyll publisher не считается выключенным от зелёного Actions job.

## M3a.2 — завершённый исторический срез

[Приватный бинарный HTTP upload/read](media-http.md) общий для человека и агента.
Explicit opt-in, без web-формы, public photo route и автоматической marketplace
регистрации. [Приёмка M3a.2 в CI](ci-m3a2.md) завершена; первый из 6 этапов ещё не завершён.


## Актуальная граница после F3a

[F3a child Landlock/seccomp](ci-f3a.md) проверен в Actions; он не доказывает поддержку
политики/нагрузки на VPS. До короткого owner-first TEST: F3b consistent DB+photos
restore/current security-state, F3c pinned dependencies/capacity/operator package,
затем отдельно разрешённые preflight → loopback → HTTPS/external checks.
[Следующая bounded задача F3b](test-candidate.md#f3b-bounded-задача-следующего-чата-spec-не-реализация).
Ни main, ни production не меняются автоматически.


## Актуализация после F3b

[Offline DB+photos recovery quarantine принят](ci-f3b.md). До fresh-only первого
VPS TEST остаётся подготовительный блок F3c: pinned dependencies, operator package
и resource/rollback acceptance. После него — отдельно разрешённые preflight →
loopback → HTTPS/external проверки. Один блок может потребовать нескольких срезов/
коммитов; это не обещание установки за один шаг. F3b требует доступного original
current security authority; независимый disaster recovery/promotion не закрыт.


## Актуализация после F3c.1

[Locked offline wheelhouse принят в CI](ci-f3c1.md): versioned hashes, чистый venv
без index, native candidate/recovery smoke. Это сокращает остаток F3c до F3c.2:
reviewed fresh-only operator plan/install/health/stop/rollback и ресурсные/disk
бюджеты. Затем три отдельно разрешаемых инфраструктурных шага: свежий read-only
preflight VPS → loopback TEST → HTTPS/external acceptance. Не обещание четырёх
команд: возможны исправления совместимости. Browser/search/replies не блокируют
этот узкий TEST, но обязательны для полного marketplace. Production не принят.


## Актуализация после F3c.2a

[Read-only operator proposal принят в CI](ci-f3c2a.md). Это concretized plan, не
готовая установка: F3c.2b lifecycle implementation/negative interruption tests и
measured resource budget остаются. Supplied host observations не доказывают
свободный порт/paths/account и не заменяют свежий owner-approved VPS preflight.
Количество инфраструктурных ворот не изменилось: preflight → loopback → HTTPS.


## Актуализация после F3c.2b

[Настоящий unprivileged offline lifecycle принят в CI](ci-f3c2b.md): установка,
проверка занятого порта/прерывания старта, authenticated loopback MCP, stop/restart
с сохранением данных и stop-only rollback.864 tests на Python3.12. Это ещё не
root-owned/systemd installer: F3c.2c должен обеспечить неизменяемый release,
проверку unit/drop-ins, cgroup cleanup и измеренные суммарные ресурсные бюджеты.
Наблюдения idle RSS не закрывают capacity gate. Затем прежние отдельно разрешаемые
шаги: fresh read-only VPS preflight → loopback TEST → HTTPS/external acceptance.
Нет обещания фиксированного числа команд или готового production. Browser writes,
публичная регистрация/search/replies и disaster-recovery cutover не включены в
сокращённый TEST и не считаются выполненными.


## Актуализация после F3c.2c.1

[Fixed unit renderer и cgroup fixture приняты в CI](ci-f3c2c1.md). Реальный systemd
на одноразовом Actions runner остановил parent и TERM-resistant child; counters
сняты для группы. Это не запуск нашего candidate под этим unit и не доказательство
достаточности VPS. Остаток F3c.2c.2: fresh root-owned installer/pre-effect checks,
реальный candidate/native photo под unit, aggregate resources/timeout/admission/
disk и interruption/state preservation. Затем отдельно разрешённые preflight →
loopback → HTTPS. Не увеличивает продуктовый MVP: browser/search/replies/admin
по-прежнему не включены в сокращённый owner-first TEST.


## Актуализация после F3c.2c.2

[Actual candidate under exact systemd unit принят в CI](ci-f3c2c2.md): настоящий
native12MP photo, body admission/timeout/disconnect, принудительный worker timeout/
reap и повторное использование slot; карточка/фото/withdraw и перезапуск сохраняют
ключ/данные/withdrawal. Kernel group peak172.625MiB в одном синтетическом сценарии.
Это больше не только fake-process proof, но ещё не production installer/capacity.
F3c.2c.3: reviewed fresh-only installer с ready-last receipt и pre-effect identity,
interruption/unrelated-service protection, capacity safety margins и full install/
state disk/retention/exhaustion runbook. Не переписывать уже принятый CI harness.
Затем прежние отдельно разрешённые fresh VPS preflight → loopback → HTTPS gates.
