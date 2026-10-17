# Source provenance and license

Repository created public under MIT at the explicit request of LeonidYasin.
The root LICENSE applies to this project. No live DB, messages, env, VPS config,
credentials, snapshots or root backups were copied.

Extracted source: LeonidYasin/mcp-server PR #116 at immutable commit
`5290a940b77d60924a9d4d53b76b7de8af9c4e83`.
[Machine-readable source paths/blob SHA/SHA-256](upstream-snapshot.json).
The source Git blob SHA was verified before local file adaptation.

- store.py: retained transactions/limits/TTL/cursor/cadence/retry/storage guards;
  replaced GitHub-only principal regex with local UUID namespace, added separate
  application_id and local users/credential tables, changed visibility label;
  additive v2 enrollment/budget tables (no embedded identity mapping).
- maintenance.py: retained consistent snapshot/verify/new-path behavior, added
  standalone application_id and identity tables to validation/counts.
- test_core.py/test_recovery.py: adapted focused embedded tests to local principals;
  GitHub-client / whole-server adapter tests are intentionally not copied as-is.
- identity/service/server/admin and auth/HTTP/CLI tests are new standalone adapters.

This is an attributed source extraction, not a preserved clone of the full original
Git history. Original repository/commits remain the history reference. Original
source did not include an explicit root LICENSE at the inspected snapshot; owner
explicitly authorized public MIT for the new project. This does not relicense all
unrelated old code or third-party contributions. Preserve any future contributor
notices and dependency licenses. The official MCP SDK is installed, not vendored;
its independent license and all transitive licenses continue to apply.

Existing embedded TEST composite and PR source SHA are different objects; neither
this repo's commit nor its CI is evidence of deployment on that VPS.
