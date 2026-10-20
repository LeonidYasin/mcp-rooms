# Documentation Pages — exact-SHA acceptance

Site/code SHA: `6fd4f7ad5b2c6271e3114a09e28a187a969f2370`.
Source: feat/standalone-identity, not main/released application.

## Build, rendering, deployment

- [Push build + deploy, attempt1](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39476009622): **success**.
- [PR build / no deploy](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39476015689): **success**.
- Strict MkDocs build; **37 source Markdown documents**, **14 registry components**.
- Browser QA log: **11 diagrams** rendered; local links/assets; mobile page overflow;
  local search; automatic dark appearance; settled mobile menu; diagram zoom; screenshots.
- Browser request gate rejects automatic external requests; no CDN/fonts/analytics/GitHub
  statistics fetches. Explicit user-clicked links to sources/GitHub are still external.
- **11 final CI PNGs inspected individually**: home/map/mindmap desktop and mobile,
  enlarged mindmap desktop/mobile, mobile menu, dark home, search results.
  Layout/reduced-motion/menu/search issues found in earlier iterations were corrected.
- Source app regression matrix3.10–3.13 remained successful; this docs change does not
  implement another marketplace/runtime feature. Runner/dependency notices are not
  claimed eliminated; full accessibility/security/supply-chain audits remain separate.

## External confirmation

[Public site](https://leonidyasin.github.io/mcp-rooms/) and
[version.json](https://leonidyasin.github.io/mcp-rooms/version.json) served the exact
SHA above after successful deployment. External manifest read confirmed source_ref
feat/standalone-identity, development channel and production=false. A follow-up
commit records this evidence and updates docs; its moving-site SHA will change.
This is not evidence of live Rooms/marketplace API, main merge or a VPS deployment.

The first successful snapshot contains37 Markdown sources; later docs-only evidence
adds another file. Version manifest counts/digests always describe its own source SHA,
not a permanently fixed document count or proof every line is functionally tested.

## Resolved initial deployment blocker

Earlier [72f0ee4 push run](https://github.com/LeonidYasin/mcp-rooms/actions/runs/39474819784)
had successful build/QA/artifact but environment protection rejected the alpha branch.
The later run above deployed successfully. The agent did not change admin settings,
create PATs, bypass protection or merge main; the precise external settings change is
not asserted. The old blocker is history, not a current instruction to weaken protection.

## Boundaries and next work

- Moving development documentation, with exact-SHA source/history links on each page.
- Git history is the version archive; no invented stable release/version selector.
- Only allowlisted public Markdown/site assets, not repository-wide file upload.
- [M2b worker/storage](media-storage-design.md) remains SPEC: next code/test slice,
  no public upload or native decoder sandbox accepted by publishing these docs.
- VPS, Caddy, runtime database, existing services and main not touched by this work.
