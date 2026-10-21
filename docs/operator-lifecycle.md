# F3c.2b — непривилегированный lifecycle rehearsal

**CI: [exact-source evidence](ci-f3c2b.md). Не root/systemd installer и не выполненный VPS deploy.**
[Общий контракт](test-candidate.md) · [План фиксированных VPS targets](operator-plan.md).

`tools/operator_lifecycle.py` реализует настоящую fresh-only офлайн-установку,
явный bootstrap, запуск кандидата на loopback8766, ограниченный health, stop и
stop-only rollback. Проверяется в Actions на синтетических данных. Это частный
operator tool, не MCP method, не web endpoint и не произвольный remote shell.

## Что выполняется

1. Linux x86_64/Python3.12, non-root real/effective UID/GID, не root group и без
   permitted/effective/inheritable/ambient capabilities. Trusted verifier повторно
   проверяет exact-source locked wheelhouse до и после установки.
2. Новый абсолютный canonical каталог под owner-only0700 parent; no reuse/alias/
   overlap. Private lock. Новый venv `--copies`; fixed argv без shell, clean env,
   no token/credentials/PYTHONPATH inheritance. pip no-index/no-deps/only-binary/require-hashes
   и pip check. Вызовы имеют deadlines; raw stdout/stderr подавляются, не попадают
   в stdout агента или artifact.
3. `install.json` ready-last содержит exact source/resource/lock hash, UID, root
   device+inode, interpreter inode/hash. fsync/partial failure не оставляют ready;
   target сохраняется для review, автоматический retry поверх него запрещён.
4. Bootstrap — ОТДЕЛЬНЫЙ явный credential-creating шаг: fixed installed CLI, новая
   profile/0700, key/0600. Controller ключ не читает/не возвращает. Для настоящего
   key необходимо отдельное разрешение; Actions key только disposable synthetic.
5. Start повторно проверяет installation receipt/interpreter/profile; занятой порт
   отказывает. Port probe не reservation: после запуска проверяется реальный
   LISTEN socketinode, принадлежащий этому PID, не просто HTTP на том же порту.
   Проверяется command digest, UID, boot ID и /proc start_ticks. Новая session,
   fixed argv, clean env, no access/stdout/stderr logs. Candidate сам проверяет
   native Landlock/seccomp до startup. Другие endpoints/services не меняются.
6. Ready process receipt пишется только после owned loopback listener и401 без
   credentials. Это transport health, **не** пользовательская auth acceptance.
7. Stop использует pidfd, не сигнал по PID из JSON. Reused/mismatched PID/boot/
   source/root/argv/UID отказывают ДО сигнала. SIGTERM и bounded wait; timeout
   требует review, не fallback SIGKILL/killall/killpg. Own children reaped.
8. Rollback — только stop нового процесса; никогда не стирать state/venv/receipts,
   не откатывать DB/ключи/revocations и не запускать recovery copy. Restart сохраняет
   stopped receipt перед новым PID record; partial/unknown records требуют review.

## Реальные границы этого среза

- Каталог rehearsal принадлежит операторскому непривилегированному пользователю.
  Interpreter fingerprint НЕ доказывает неизменность всех site-packages/dynamic
  libraries. Same-UID hostile writer исключён из границы: это не root-owned immutable
  release из будущего VPS-плана. Не использовать код как готовый public production supervisor.
- PIDfd защищает адресата сигнала от PID reuse, не является cgroup supervisor.
  `descendants_supervised=false`: полное завершение/учёт orphan native descendants
  после crash не обещаются. Нужен отдельный systemd KillMode/control-group gate.
- Отсутствие чужого listener проверено при старте, но непривилегированный инструмент
  не может резервировать порт за будущим процессом. Если спорный listener/identity/
  receipt/boot — отказ; не убивать соседний процесс для освобождения порта.
- Observation JSON из предыдущего плана не является полномочием. Этот код не создаёт
  Unix accounts/units, не меняет root directories/permissions, Caddy/HTTPS/autostart.
- Idle RSS point sample и maximum RSS одного reaped child в CI — только наблюдения
  конкретного rehearsal, НЕ combined parent+native peak/stress/cgroup MemoryMax/
  диск или гарантированная ёмкость VPS. Resource acceptance остаётся false.
- Health401 не authenticates client. Отдельный CI smoke делает настоящий synthetic
  authenticated MCP initialize/tools/create/get, restart и stop-only rollback,
  сохранность чужого listener и cleanup после interruption перед ready marker;
  это не внешний пользовательский VPS acceptance и не native photo network benchmark.

## Следующий оставшийся gate

F3c.2c: fixed root-owned/systemd обёртка по [operator plan](operator-plan.md),
сверка реальных unit/drop-ins/process/path identities перед эффектами, cgroup
child cleanup, interruption/other-service protection, measured aggregate resources/
timeout/admission/disk и новый owner-reviewed runbook. Без auto-delete/recovery promotion.
Затем отдельно разрешённые fresh read-only VPS preflight → loopback TEST → HTTPS.
Любая remote execution требует отдельного согласия И специального пароля владельца.

Полная install.lock closure устанавливается с --no-deps, чтобы не резолвить
дополнительные/direct-URL METADATA dependencies; затем pip check. Хеши не
сертификат отсутствия вредоносного кода и не OS network-isolation sandbox.
