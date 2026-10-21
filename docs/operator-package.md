# F3c.1 — закреплённый офлайн wheelhouse

**SOURCE, runtime hash-lock принят отдельным commit; ожидает locked Actions. Не VPS installer.**
[Контракт этапа F3c](test-candidate.md), [F3b recovery limits](recovery-candidate.md).

## Назначение

`tools/operator_bundle.py` готовит только публичный пакет wheels для Linux x86_64,
CPython3.12. Не импортирует приложение, не создаёт профиль/ключи, не выполняет
systemctl/useradd/Caddy/SSH. Кросс-платформенность core3.10–3.13 сохраняется;
operator artifact намеренно проверяется для одного целевого runtime.

1. Discovery (если versioned runtime lock отсутствует): pip download только binary
   wheels для собственного wheel[media]. Формируется proposed exact lock с SHA256.
   Пакет помечен discovery-not-installable, обычный verifier его отвергает.
2. Принятие lock — отдельный reviewed commit, не auto-upgrade и не pip freeze
   окружения с Qwen/dev tools. Только серверные runtime dependencies + Pillow.
3. Locked build: pip download --require-hashes --only-binary, версия/хеш каждого
   transitive dependency из repo lock. Собственный project wheel привязан к source
   SHA и получает отдельный hash в generated install.lock.
4. Включаются только wheels/runtime.lock/install.lock/manifest.json/OPERATOR.md.
   Запрещены extra files, aliases, unsafe modes/names/target, duplicate dists,
   corrupted bytes/metadata/lock, source/hash mismatch. Bounded80 wheels,48MiB/file,
   192MiB суммарно, manifest/lock128KiB, wheel METADATA256KiB. Никаких DB, env, real keys/photos/logs.
5. Новое venv в Actions устанавливается с --no-index --find-links --require-hashes
   --only-binary; pip check и native candidate+recovery smoke из установленного
   wheel. Ни Qwen requirements, ни pytest/dev deps для этого не устанавливаются.

## Цепочка проверки

Generated manifest: exact source SHA, целевая платформа, distributions/name/version/
wheel/hash/size и hash каждого allowlisted файла. Внешний SHA256 tar.gz печатается
в CI и фиксируется в evidence; source-помеченный artifact хранится14дней.

Нельзя доверять одному manifest из неизвестного архива: checksum — не signature.
Сначала сверить tar.gz с доверенным exact-SHA CI, затем private extraction и verifier
с independently supplied expected source SHA/runtime lock hash. Никакой повторной
загрузки «недостающего» пакета при офлайн install.

## Не закрывает F3c целиком

Python/pip/venv, glibc, Landlock/kernel — отдельные host prerequisites. Wheels
проверяются pip на реальной совместимости; это не доказательство доступности VPS.
Build tools и вся ОС не объявлены воспроизводимыми/захешированными этим lock.
Dependency hashes не заменяют review/vulnerability monitoring или подпись поставщика.

F3c.2: reviewed fresh-only dry-run/install/health/stop/rollback и ресурсные/disk
бюджеты. Не задавать MemoryMax по старому отчёту VPS. Restore outputs остаются в
карантине: не делать promotion копированием profile.json. Main/production не менять.
После кодовой приёмки — отдельные разрешения на preflight/loopback/HTTPS; для каждого
remote execution нужны явное согласие и специальный пароль.

## Происхождение runtime lock

Discovery source `22a248751e0118b300ddb6cd99e54891edcda921`,
[Actions attempt1](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39596126281).
Рассмотрены30 уникальных server runtime distributions (не pip freeze dev-окружения),
включая mcp1.26.0 и Pillow13.0.0. Версии и единственный hash wheel каждой зависимости
явно записаны в `operator/runtime-linux-x86_64-py312.lock`.
SHA256 lock: `05f7fd5ba929c68b25b46649c25a8868834e50834d6cc0ba9addd15e411de536`.
Это фиксация resolver output и проверяемых байтов, не сертификат отсутствия CVE.
Изменение lock требует нового review/commit и полного offline smoke.
Discovery artifact не принимается для установки; нужен новый locked build.

Первоначальный discovery корректно отказал: Pydantic2.14.1 METADATA133006bytes
превысил общий128KiB лимит. Введён отдельный256KiB бюджет только wheel METADATA,
с regression acceptance/refusal cases; manifest/lock budget128KiB не увеличен.
