# MCP Rooms — офлайн wheelhouse, не VPS installer

Только Linux x86_64, CPython3.12. Это набор точных wheels и hash-lock,
а не разрешение/скрипт root-установки. Реальные данные/ключи здесь отсутствуют.
Default CLI rooms-only; marketplace candidate остаётся explicit opt-in.

1. Получить artifact **точного принятого source SHA/attempt** из Actions. Сверить
   SHA-256 tar.gz с доверенным CI/evidence, а не только с manifest из того же архива.
   Manifest/checksums не являются подписью. Discovery package не принимать.
2. Распаковать только проверенный архив в НОВЫЙ приватный каталог (0700).
   Не выполнять непроверенный код или tar из произвольного сообщения участника.
   Доверенный verifier из repo сверяет expected source SHA и SHA-256 versioned
   runtime lock, все wheels/файлы и отсутствие лишних объектов/aliases.
3. Только в отдельно согласованном новом venv: pip install с --no-index --no-deps,
   --find-links на wheels, --only-binary=:all:, --require-hashes -r install.lock.
   Затем pip check. Нельзя убрать hash-checks/скачать недостающий пакет из сети.
4. Python/pip/venv, glibc и kernel/Landlock — host prerequisites, не включены в
   wheelhouse. ABI compatibility реально проверяет pip; конкретный VPS ещё не
   проверен. Supply-chain review и обновления lock — явные commits/CI, не auto-latest.

Никакого systemctl, useradd, Caddy, bootstrap credentials, public route или удаления
данных этот пакет не выполняет. Следующий F3c.2 должен подготовить reviewed fresh-only
install/dry-run/stop/rollback с resource budgets, затем отдельные разрешения на VPS
preflight, loopback и HTTPS. Каждая remote execution — отдельное подтверждение и
специальный пароль владельца. Main/release/production не меняются автоматически.

Восстановленные F3b копии в карантине. Не добавлять profile.json, не выдавать старые
ключи и не запускать их как fresh state. Полный disaster recovery/promotion отдельно.

Полная dependency closure перечислена в install.lock; --no-deps запрещает повторный
resolver traversal, включая direct-URL Requires-Dist из METADATA. pip check затем
проверяет установленную closure. Это не OS-level запрет сети или гарантия
отсутствия вредоносного кода в hash-pinned third-party wheel.
