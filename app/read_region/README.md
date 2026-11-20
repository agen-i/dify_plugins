# Original-image region Tool — Dify1.20 New Agent

One managed Tool plugin. It accepts the authorized native input-file locator and optional normalized left/top/right/bottom coordinates. Omit coordinates for the full original image. A crop keeps the original source pixels; it does not resize, interpolate, OCR or invent high-resolution detail. Coordinates refer to the original after EXIF orientation.

Install the single `read_region-0.4.3.difypkg` through normal managed plugin installation, enable `read_region` in a stock New Agent, and choose a model supporting vision and tool calling. User inputs are an image and a question; native file locators are handled by the platform, not entered as user IDs.

Use the stock Dify1.20 New Agent with a vision-capable model and native `read_media`. The model must use `read_media` on the returned tool-file locator so the actual PNG enters its next vision context. A UI attachment/BLOB alone is not proof. Classic/1.18 paths that forward only text/UI files are unsupported. The user's actual deployment version must be checked; this plugin does not upgrade Dify.

The Tool takes `source_image` from the current job's authorized native file references, plus optional `x_min,y_min,x_max,y_max` in[0,1]. No URL, file ID, provider credential, app JSON, environment setup, registry, run/session ID, custom strategy or OCR service is required. The managed SDK's authenticated upload-grant metadata RPC supplies the native origin. Only one fixed-name metadata request is made; the grant is discarded without HTTP upload or file creation. No inherited environment URL or hardcoded topology is used; missing/mismatched native context fails closed.

The fetcher permits only that authenticated native origin, `/files/<UUID>/file-preview` and the exact timestamp/nonce/sign signature fields. It bypasses proxies, follows no redirect and relies on the Dify server to verify the signed bearer capability. A marker dictionary is not authorization. Remote URLs, arbitrary paths and derived tool-file inputs are rejected; each new crop must use the original upload.

Limits:15MiB input,20million decoded pixels,12,000px maximum source side,10MiB output PNG, bounded20-second download. Oversized output fails and asks for a narrower crop; there is no silent downsampling. 16-bit grayscale PNG samples and valid integer tRNS transparency remain intact through full/crop output; other16-bit PNG color modes are explicitly rejected before a lossy conversion. Image metadata is stripped from output. Existing Dify storage/model-provider retention still applies; no new cross-invocation isolation or whole-system zero-retention claim is made.

Local checks/build from repository root:

```sh
uv sync --project app/read_region --frozen
uv run --project app/read_region pytest app/read_region/tests -c app/read_region/pyproject.toml
uv run --project app/read_region ruff check app/read_region
# Use official dify CLI0.6.10 or a verified compatible CLI:
dify plugin package app/read_region -o app/read_region/read_region-0.4.3.difypkg
```

The target source contract is Dify1.20.0 commit`7bef4e1b2dc21b2c694d3243425dd3fa6288f916`: `api/core/app/workflow/file_runtime.py`, `api/controllers/files/upload_file_delivery.py`, native New Agent tools-layer/read_media image handling. Source-pixel tests are independent of native Agent vision-path acceptance. No live customer images, signed URLs or credentials are included.

## Verified path and rollback

[Managed vision proof](verification/managed-vision-proof.json) records a normal managed install and one stock New Agent's five model calls: full-image Tool output → native read_media → actual2048×1536 image in the next provider request, then original-pixel crop → read_media → actual400×300 ROI in the next request. Image-only markers and source-pixel comparisons distinguish real image context from OCR, output text or a UI attachment. The deterministic vision/function-calling test provider establishes transport only; real-model reading quality is not guaranteed.

To roll back, remove this Tool from the experimental Agent and uninstall the package only after checking other consumers. Derived files and model/Dify retention remain governed by the platform. This plugin has no service, registry, private profile or external SDK process to stop.

Historical version0.4.2 preserves native16-bit grayscale values and rejects unsupported16-bit PNG color modes. The managed vision-path proof was recorded on0.4.1; the change is isolated to pixel-mode handling, with focused full/crop sample-value regressions. SDK transport, native file authorization, output type and ordinary8-bit paths remain unchanged.

## Source and support

Source repository: [agen-i/dify_plugins](https://github.com/agen-i/dify_plugins). Report support issues through [GitHub Issues](https://github.com/agen-i/dify_plugins/issues). Public organization contact: [contact@agen-i.com](mailto:contact@agen-i.com), as listed on the [official organization profile](https://github.com/agen-i). No support address was inferred from a private deployment.

Version0.4.3 uses plugin identity `agen-i/read_region`; this is a new namespace rather than an automatic upgrade of `tkosht/read_region`. Install/bind the new Tool explicitly and use the matching workflow. Do not automatically uninstall an older package used by other apps. Runtime image/fetch code and original copyright notices are unchanged. The manifest `repo` field is supported runtime metadata; `contact` is retained for the official Marketplace validator, not a runtime-consumed field. No Marketplace publication is performed. Historical vision proofs retain their actual older publisher/version and are not relabeled as a new namespace test.
