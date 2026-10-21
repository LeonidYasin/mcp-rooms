# F3a — обязательная изоляция native photo child

**SOURCE, ожидает exact-SHA Actions. Не VPS TEST и не production.**
Дополнение [fresh candidate](test-candidate.md); предыдущая приёмка [F2](ci-f2.md)
остаётся исторической. Никакие системные настройки VPS этим кодом не изменяются.

## Механизм и граница доверия

Вместо нового демона/контейнерного стека: Linux Landlock ABI≥3 и seccomp BPF.
Только Linux x86_64, 64-bit Python≥3.11, установленный Pillow13.0.0; процесс
непривилегированный, real/effective/saved UID одинаковы, effective/permitted/
inheritable/ambient capabilities нулевые. Фактический ABI проверяется syscall,
а не строкой версии ядра. ABI3 появился в Linux6.2; LSM должен быть доступен.
Нет sudo, bubblewrap, shell, установки пакетов или требования user namespaces.

1. Parent: фиксированный child `python -I -B -m mcp_rooms.media_worker_child`;
   clean env, cwd `/`, close_fds, только stdin/stdout pipes, stderr DEVNULL.
2. Child: существующие RLIMIT (AS512MiB, CPU3s, FSIZE0, NOFILE32, NPROC0, CORE0).
3. До Pillow и входных байтов: no_new_privs → Landlock → seccomp.
4. Landlock обрабатывает все filesystem rights ABI3, включая REFER/TRUNCATE.
   Разрешены только READ_FILE/READ_DIR установленной Python stdlib/site-packages,
   фиксированных system library directories и `/etc/ld.so.cache`. State внутри
   разрешённого дерева или дерево внутри state — ошибка политики.
5. seccomp проверяет architecture, убивает foreign ABI/x32, запрещает socket
   (INET/INET6/UNIX), io_uring, exec/fork/clone, сигналы другим процессам, ptrace/
   process_vm/pidfd, namespaces/mount/handles и перечисленные kernel interfaces.
   Дополнительно запрещены chmod/chown/xattr/utime, ioctl/fcntl/flock: Landlock
   ABI3 сам не защищает эти операции. Все syscall номера≥450 запрещены до review.
6. Только после успешной установки обеих политик импортируется native decoder.

Parent сохраняет filesystem/network доступ. Ограничения не применяются к parent
и не выдаются за sandbox всего сервиса. Нет client-selected команды/allowlist;
единственный путь — доверенный operator state root, не поле запроса.

## Fail-closed и совместимость

Candidate `compose()` выполняет отдельный health child до создания приложения:
проверяет запрет чтения state/DB/marker/доставочного ключа и трёх socket families.
Каждый последующий decode child повторно устанавливает policy. Отсутствие ABI,
architecture/capabilities mismatch, отказ seccomp/прав или malformed probe дают
типизированный отказ, а не запуск без защиты. Слот немедленный, worker/upload по1;
8s deadline, ограниченные pipes, kill process group/reap/close в finally сохраняются.

Внутренний `PhotoWorker(sandbox=None)` оставлен для прежних контрактов и unit fixtures;
**candidate не использует этот режим и не переключается на него при ошибке**.
Python3.10 остаётся core-only. Bootstrap не декодирует фото; запуск candidate
в неподдерживаемой среде запрещён. Предварительная готовность VPS не предполагается.

## Доказательства Actions

`tests/test_media_sandbox.py`: реальный отдельный child пытается читать synthetic
ключ/БД/marker и внешний секрет, писать и менять metadata, создавать sockets/
процессы, посылать сигналы и вызывать запрещённые syscall. Parent проверяет
неизменность содержимого/прав/владельца/mtime/ctime, остаётся работоспособным.
Есть реальная PNG/JPEG нормализация после lockdown, unavailable-policy, timeout,
reap/slot release/no-fallback. `tests/test_test_candidate.py` проверяет отказ startup
и освобождение profile lock. Installed-wheel smoke из `/tmp` использует тот же
candidate с настоящим native decode; synthetic fixtures, без реальных фото/ключей.
Linux native CI не пропускает тесты только потому, что Landlock недоступен.

## Ограничения и дальнейшие gates

Это defense-in-depth, **не VM, не полная syscall allowlist и не сертификация**.
Landlock ABI3 не скрывает stat/chdir/access metadata. Разрешённые library trees
читаемы целиком; не помещать туда секреты. Уже открытые FD не защищаются Landlock:
поэтому close_fds и только pipes обязательны. Уже загруженные библиотеки, kernel
exploits, скомпрометированный trusted parent/host или hostile same-UID процессы
не объявлены решёнными. Установка/библиотеки должны быть operator-controlled.
Не поддерживается произвольная architecture и привилегированный/root child.

Отдельно остаются F3b: согласованный DB+photos restore с актуальными revoke/disable;
F3c: dependency pins, общий RAM/CPU/disk budget и reviewed operator package.
Ни один green CI не разрешает удалённый probe/install: требуется отдельное
согласие владельца и специальный пароль для каждого исполнения на VPS.

## Первичные источники

- [Linux6.2 Landlock UAPI, ABI3 rights/FD/metadata limitations](https://github.com/torvalds/linux/blob/v6.2/include/uapi/linux/landlock.h).
- [Linux seccomp filter: no_new_privs, architecture и границы sandbox](https://docs.kernel.org/userspace-api/seccomp_filter.html).
