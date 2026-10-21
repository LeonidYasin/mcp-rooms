# Текущее состояние MCP Rooms

Проверено для исходного SHA `88eabfb35aa7cc763d85352e3e67a48e9d5fb97f` в ветке
`feat/standalone-identity`. Это состояние кода и CI, **не работающий production**.

## Проект в одном абзаце

MCP Rooms — MCP-first площадка «Хочу / Предлагаю». Основной способ работы пользователя
с площадкой — чат со своим ИИ-агентом. Агент получает ограниченные MCP-инструменты и по
явному поручению пользователя создаёт черновик, добавляет фото, показывает точный
предпросмотр, публикует и снимает объявление. Web на текущем этапе — публичная
**витрина только для просмотра** уже опубликованных карточек и фотографий. Web-форма,
кабинет, каталог с записью и cookie-authorized редактирование пока не являются частью
ближайшего результата.

## Что реализовано

### Основа доступа и общения

- локальные UUID-пользователи без обязательного GitHub/email/телефона;
- digest-only Bearer-ключи, scopes, срок действия, отзыв и блокировка пользователя;
- 8 MCP-инструментов общих Rooms;
- 12 opt-in MCP-инструментов объявлений;
- официальный MCP Python SDK и Streamable HTTP;
- SQLite как единое локальное хранилище.

### Объявления и фото

- приватный черновик, категории, revision CAS и идемпотентные команды;
- безопасная загрузка JPEG/PNG и перекодирование без метаданных;
- приватное файловое хранилище, квоты, staging, cleanup и проверка владельца;
- точный preview конкретной версии;
- отдельное согласие на публикацию;
- публикация, публичная allowlist-проекция и снятие объявления;
- анонимная read-only HTML-карточка и публичные производные фото.

### Эксплуатационная подготовка

- Linux sandbox декодера: Landlock/seccomp, rlimits и bounded worker;
- offline DB+photos recovery в новую закрытую карантинную копию;
- hash-pinned offline wheelhouse;
- fresh-only root-trusted установка без неявного bootstrap/start;
- фиксированный systemd unit и cgroup harness;
- отдельный guarded controller для capacity check, bootstrap, start и stop;
- отказы при занятом порте, unit/drop-in/path/process drift и прерванном старте;
- stop сохраняет БД, фото, ключи и receipts.

## Что подтверждено

На SHA `88eabfb35aa7cc763d85352e3e67a48e9d5fb97f` успешно завершены:

- CI на Python 3.10, 3.11, 3.12 и 3.13;
- build wheel/sdist и import установленного wheel вне checkout;
- installed owner-first candidate smoke на поддерживаемых версиях;
- operator systemd supervision proof с реальным disposable systemd/cgroup fixture;
- GitHub Pages/documentation workflows.

Это подтверждает код и синтетический Actions-сценарий. Это **не** подтверждает ёмкость
конкретного VPS, внешний HTTPS, реальный ключ, публичную регистрацию или production.

## Что пока не сделано

- production MCP Rooms и постоянно работающий endpoint;
- открытая регистрация и безопасное восстановление потерянного доступа;
- запись через браузер: формы, кабинет и cookie-authorized market/media commands;
- общий публичный feed/search;
- приватные отклики и переговоры;
- отдельный admin MCP и модерация;
- полный независимый disaster-recovery cutover без исходной current authority;
- измеренная ёмкость конкретного VPS, off-host backup и production runbook.

## Текущая граница

Код F3c.2c.3b — guarded bootstrap/start-stop controller и принятые runtime/disk
критерии — присутствует в HEAD и прошёл Actions. Предыдущий `work-state.json` отставал
и всё ещё называл этот срез следующим. Данное обновление закрывает расхождение:
принятый application source SHA становится `88eabfb…`; docs-коммит сверху не меняет
принятый source SHA.

## Следующий шаг

Следующая крупная точка — **fresh isolated owner-first TEST**:

1. отдельно разрешённый read-only preflight конкретного VPS;
2. новая отдельная установка без использования старой Rooms TEST DB;
3. loopback synthetic acceptance;
4. только после отдельного разрешения — временный HTTPS и внешний MCP-клиент;
5. публикация одной реальной карточки с реальными фото и явным согласием владельца;
6. снятие карточки, остановка TEST и сохранение evidence.

Каждое удалённое действие требует отдельного разрешения владельца и специального
пароля. Merge, release и production — отдельные решения.
