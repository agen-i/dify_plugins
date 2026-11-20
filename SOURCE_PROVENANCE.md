# Source provenance

- Upstream: https://github.com/tkosht/dify_plugins
- Source commit: `2388e1b94dada49286e28b468e5e15dec473efb8`
- Source visibility at copy time: public.
- Copy semantics: new independent repository; no ownership transfer and no upstream history rewriting.

The five plugin directories under `app/` and their functional tests are copied from this source only. `SOURCE_FILES.json` records the original paths and SHA-256 hashes. New files are minimal uv environment definitions/locks and repository usage/provenance documentation. The PDF plugin's existing environment and lock are retained. Necessary Black formatting is the only plugin Python source change. The nanobana development guide now instructs creating an uncommitted local environment file and starting with uv, because environment examples are excluded from this copy.

The upstream root `LICENSE` is retained verbatim, including “Copyright (c) 2025 Adoptive Market Crawler”. The PDF-specific `LICENSE`, `third_party/` license notices, assets, security/privacy documentation and already-public distribution packages are retained. No private inventory code or private generator material is included.

Unrelated template harnesses/docs, Docker/devcontainer tooling, old publishing workflows and all environment files (including environment examples) are omitted. Plugin author/name identifiers and attribution remain unchanged to preserve package compatibility. Existing package deployment or external service acceptance is not implied by local unit tests.

## read_region transfer (2026-11-21)

`app/read_region` is transferred separately from public `tkosht/dify_plugins` commit `08d8ba405aff64871e06a41bd77c21447da52d95` (merged vision PR117). Only current source/tests/locks/license/privacy, sanitized verification and the0.4.2 distribution are included; prior0.4.1 binaries, old OCR/strategy trees, runtime data and user kits are not copied. The exact0.4.2 package SHA256 is `e355c64596b9c6492fd8e1e952d0e6780a5be2ef53e3bc4868591a9e4afd962a`. Plugin author/name remain unchanged for compatibility. `app/read_region/SOURCE_SHA256.json` records this component; the earlier five-plugin inventory above remains historical. Target CI uses the component's independent locked environment. The prior managed0.4.1 vision-path evidence remains labeled as such;0.4.2 adds unit-verified native16-bit grayscale/tRNS preservation without claiming a new live deployment.
