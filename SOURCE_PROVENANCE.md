# Source provenance

- Upstream: https://github.com/tkosht/dify_plugins
- Source commit: `2388e1b94dada49286e28b468e5e15dec473efb8`
- Source visibility at copy time: public.
- Copy semantics: new independent repository; no ownership transfer and no upstream history rewriting.

The five plugin directories under `app/` and their functional tests are copied from this source only. `SOURCE_FILES.json` records the original paths and SHA-256 hashes. New files are minimal uv environment definitions/locks and repository usage/provenance documentation. The PDF plugin's existing environment and lock are retained. Necessary Black formatting is the only plugin Python source change.

The upstream root `LICENSE` is retained verbatim, including “Copyright (c) 2025 Adoptive Market Crawler”. The PDF-specific `LICENSE`, `third_party/` license notices, assets, security/privacy documentation and already-public distribution packages are retained. No private inventory code or private generator material is included.

Unrelated template harnesses/docs, Docker/devcontainer tooling, old publishing workflows and all environment files (including environment examples) are omitted. Plugin author/name identifiers and attribution remain unchanged to preserve package compatibility. Existing package deployment or external service acceptance is not implied by local unit tests.
