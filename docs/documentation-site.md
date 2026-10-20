# Сайт документации: обновления, версии и публикация

## Назначение

GitHub Pages — публичная карта проекта и читаемая документация, **не** backend Rooms,
не маркетплейс, не место регистрации/ввода ключей, не публикация объявлений или переписки.
Ожидаемый адрес после успешной настройки/деплоя: https://leonidyasin.github.io/mcp-rooms/ .
Наличие файла workflow или зелёного build само по себе не подтверждает доступность URL.

Основа: MkDocs1.6.1 + Material9.7.7 (MIT), Mermaid12.2.0 (MIT); сборка в GitHub Actions,
отдельно от runtime зависимостей. Шрифты системные, скрипты/поиск/схемы локальные,
никаких Google Fonts/CDN/аналитики/API ключей. Набор прямых зависимостей закреплён;
это не полный lock транзитивных зависимостей и не supply-chain аудит.

## Источники истины

- `docs/project-status.json`: единый реестр компонентов, stage, зависимости, doc/source/evidence.
- `docs/product-mindmap.md`: подробная продуктовая карта; `architecture-graph.md`: trust/data/ER.
- `docs/delivery-plan.md`, `ROADMAP.md`: порядок работ и оставшиеся gates.
- `docs/ci-*.md`: exact-code-SHA evidence. CI прошлого SHA не объявлять свежей проверкой нового кода.
- `tools/docs/prepare.py`: проверяет реестр/циклы/пути и собирает страницы без импорта приложения.

Новый компонент/изменение статуса включает правку реестра, документа/теста/evidence в
одном reviewed изменении. SPEC → SOURCE → CI → TEST → PROD не взаимозаменяемы.
PROD сейчас не выставлен ни одному компоненту. TEST обозначает исторический пилот,
не запущенный сейчас сервис. Карта не является автоматически вычисленным code coverage.

## Что значит версионирование

Вся документация хранится в Git вместе с кодом. На каждой странице — короткий SHA,
ссылка на **полный точный commit** исходника и история файла. `version.json` содержит
source SHA/ref/channel/build time и SHA-256 исходных Markdown. Читатель может восстановить
любой опубликованный снимок из этого Git SHA; изменения страницы не переписывают историю.

Это moving development site, **не** каталог released versions. Релизных веток/тегов
документации пока нет; не придумывать stable/v1.0. До релизов архивные версии читаются
в GitHub по SHA; сборочные preview artifacts имеют срок14 дней и не вечный архив.
Позже выбранные релизы можно опубликовать под `/versions/<tag>/` отдельным решением.
История SHA и последний успешный runtime CI — разные ссылки и разные утверждения.

## Как обновляется

Workflow `Documentation Pages`: push в `feat/standalone-identity` → подготовка → strict
MkDocs build → ссылки/реальный Mermaid render/mobile/search QA → artifact → Pages deploy.
PR делает build/QA без pages-write/deploy. Не используется pull_request_target, нет PAT
в workflow, нет VPS/SSH/секретов, ни merge, ни release не выполняются.

Пока источник ровно alpha-ветка. После согласованного merge в main поменять branch
allowlist/checks одним reviewed коммитом; не разрешать одновременно старой alpha-ветке
и main перезаписывать один сайт в произвольном порядке. Concurrency отменяет старую
публикацию. Удалённая ветка/отключённый Actions не означают автоматическое обновление сайта.

## Однократная настройка владельцем

1. Repository Settings → Pages → Source: **GitHub Actions**.
2. Если environment `github-pages` ограничен main, разрешить deployment именно из
   `feat/standalone-identity` для сайта документации. Не отключать остальные защиты;
   approval владельца, если настроено, остаётся обязательным.
3. Открыть Actions → Documentation Pages и проверить **build и deploy**, затем HTTPS URL
   и `version.json` с ожидаемым SHA. При первоначальной настройке достаточно rerun
   неуспешного workflow. Если workflow_dispatch ещё не виден из-за отсутствия workflow
   в default branch, не мержить приложение ради кнопки: push в разрешённую ветку запускает сборку.

Стандартный GITHUB_TOKEN не может включить Pages впервые через configure-pages enablement.
В подключённом MCP нет Pages settings API; отдельные admin credentials/новые PAT не нужны.
Без настройки честный статус — «сайт собран, публикация заблокирована настройкой», не «Pages включён».
[GitHub custom workflow guide](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages),
[configure-pages inputs](https://github.com/actions/configure-pages/blob/v5/action.yml).

## Защита публичной сборки

Выборка: README/ROADMAP, Markdown docs и Qwen README, отдельные проверенные site-assets.
Остальной repo не выкладывается целиком. Относительные ссылки на код/пример конфигурации
ведут к GitHub blob точного SHA, не копируют его на сайт. Нет `.env`, DB, snapshots,
приватных логов/ключей/вложений пользователей. Текст уже публичной документации проверять
перед коммитом: копирование публичного Markdown не делает секреты безопасными.

GitHub Pages — статический хостинг; backend security/abuse gates для marketplace не
заменяются защитами docs workflow. Пока нет полноценного offline release archive,
а strict build и browser smoke не являются полным аудитом доступности/безопасности.
