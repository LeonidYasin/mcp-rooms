# M2a CI evidence — optional photo normalizer / opportunity vision

Code SHA: `110393e90240a1a534e87a15fb23496fc77b8a28`.
Branch: feat/standalone-identity, PR #1. No merge or deploy performed.

- Exact-SHA aggregated checks: **8/8 success**, push + PR, Python3.10–3.13.
- [Push run, attempt1](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39471384843).
- [PR run](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39471391351).
- Retrieved Python3.12 log: **267 passed, 2 warnings in 4.96s**;
  Pillow13.0.0 installed, wheel/sdist built, outside-source installed-wheel imports passed.
- Retrieved Python3.10 test step: **247 passed, 1 skipped, 2 warnings in 5.77s**.
  The skipped item is the optional media module, not an unreported media pass.
  Media CI legs3.11–3.13 explicitly install the extra and import its module.
- Python AST preparation only locally; no project imports/tests/server on the agent
  computer or VPS. Warnings are not claimed fixed. Docs-only follow-up records this
  tested runtime SHA; it does not substitute its own SHA as a tested code revision.

## Accepted scope

Twenty synthetic media test cases extend the previous247: JPEG/PNG conversion, fresh
JPEG and hash/dimensions, PNG text removal, alpha flattening, EXIF rotation without
forwarding metadata, resize/no upscale, byte/type/MIME rejection, corruption/truncation,
APNG rejection, input/dimension/output bounds and retained Pillow bomb warning guard.
Existing room/identity/draft/lifecycle/intent regression remains green.

## Still not accepted

No public upload, OS decoder isolation, media storage/ownership/retention, real photos,
listing media references, public publication, web forms, private replies, admin MCP,
load/abuse/resilience audit or production. Removing metadata is not removing visible
personal data or proving authenticity. [Full safety boundary](media-image-safety.md).

The expanded [opportunity model](opportunity-model.md) is documented intent, not newly
implemented jobs, talent, startup or investment functionality. About text is supplied
for the owner's manual edit; repository metadata has not been changed by this work.
