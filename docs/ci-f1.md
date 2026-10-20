# F1 CI evidence — read-only published card and shorter owner-first TEST

Accepted application source:
[`c086805e79a788e63c8df9093c9a0bf50c95b479`](https://github.com/LeonidYasin/mcp-rooms/commit/c086805e79a788e63c8df9093c9a0bf50c95b479).
Later documentation checkpoints do not replace this accepted runtime source.
Contract and reduced deployment scope: [owner-first TEST](owner-first-test.md).

## Exact-source verification

- [Push application CI, attempt1](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39511067019): success, Python3.10–3.13, wheel/sdist and installed-package checks.
- [PR application CI](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39511074250): same-source matrix success.
- Python3.12: **645 passed, 2 warnings**;22 additional HTTP/contract cases over M3b.2.
- Python3.10: **595 passed, 31 skipped, 2 warnings**. Optional native media remains >=3.11.
- [Documentation build/QA/deploy](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39511067023):15 diagrams, local links/assets, mobile overflow, Cyrillic search and screenshots passed.
- SHA-wide inspection:14 successful checks,1 skipped,0 failed/pending. Skipped is not a passing test or permission to merge.
- Earlier source `cac12ef28d3c4f618618692c4ef10b1d161ad28b` also passed (643 tests on3.12); final source adds visible fulfilment modes and explicit old-v1-consent rejection. No failing test was removed or weakened.

Application/native/package and documentation/browser work ran in Actions only.
Local work was text/AST inspection, not pytest/import/build/server/browser execution.
All users, keys, listings and derivatives in tests are synthetic. No real VPS request,
credential issuance, listing publication, main merge or release occurred.

## Accepted boundary

Explicit `public_market=True` composition over the existing bound market adapter;
default rooms-only CLI unchanged. Anonymous GET-only HTML card and epoch-bound JPEG
use fresh `PublicationStore` availability/integrity checks. Escape all participant
text; static SHA-hashed CSS, no JS/remote assets/forms/CORS/raw HTML/autolinks. Strict
configured Host/query policy; cross-site public navigation does not bypass private
credential/origin gates. Cookie/Bearer do not change public authority.

Tested through actual user MCP: stage synthetic fixture/attach → fresh preview and
consent → publish → anonymous HTML/photo → cross-owner withdrawal denial → owner
withdrawal →404 for both. The new HTTP suite uses a synthetic worker derivative;
it is not a native image/browser screenshot acceptance. Existing native/race suites
still run on supported matrix versions. Separate real-image/browser/HTTPS/load tests
remain required on the installable candidate before external launch.

Negative checks cover private/missing/disabled/damaged data, wrong epoch, bad Host,
query secrets, unsupported methods, default-off composition, no implicit cookie
writes, bounded global request admission/minute budget and sanitized503. Cards
show actual title/description/category/price/location/fulfilment/photos, no fabricated
reviews/seller verification or dead purchase/chat button. Private identity fields
are not rendered. v2 notice replaces misleading future-transport wording; v1 consent
cannot authorize a new v2 publication. Preview transport field null means unknown to
core, not endpoint discovery. Downloaded copies cannot be withdrawn retrospectively.

## Not accepted / next bounded task

F2: fresh strict state/composition/bootstrap and pinned artifact, one decoder/upload
slot for small TEST, no automatic serve-time migration/repair or real key issuance.
Then OS filesystem/network/resource acceptance, DB+files backup/restore with revoked
security-state reconciliation, reviewed rollback and owner-approved fresh VPS
preflight/install. Old rooms-only rollout scripts must not be reused as a marketplace
installer. Three major gates are **not** three shell commands or a time estimate.

No feed/search, browser editor/onboarding, in-app private response, admin MCP, fleet
anti-bot or production readiness is claimed. Browser M3b.3 is preserved as a paused
mandatory prerequisite before cookie-authorized market/media writes. Full six-stage
pilot remains a separate larger target. Pages is documentation; the owner-controlled
[single-publisher gate](ci-pages.md#remaining-single-publisher-configuration-gate) is unchanged.
