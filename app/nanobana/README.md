## nanobana

**Author:** tkosht
**Version:** 0.1.1
**Type:** tool

Generate and edit images with Gemini Nano Banana models from Dify workflows.

### Authentication

The plugin supports two authentication modes.

- Vertex AI: set `vertex_project_id`; optionally set `vertex_location` and a base64-encoded service account key JSON. Leave the service account key empty to use Application Default Credentials.
- Gemini Developer API: leave `vertex_project_id` empty and set `api_key`.

If both are configured, Vertex AI is used.

### Models

- `gemini-3-pro-image` is the primary/default model for this plugin.
- `gemini-3.1-flash-image`

Only the current GA model IDs are exposed.

### Tool parameters

- `prompt`: required image prompt.
- `images`: optional input images for editing or visual reference.
- `model`: Gemini image model.
- `aspect_ratio`: generated image aspect ratio.
- `resolution`: generated image size. Pro-first workflows should use the Pro-compatible resolutions `1K`, `2K`, and `4K`.

### User-side Vertex test

Automated unit and package tests do not perform live Gemini Developer API or Vertex AI calls. To verify real authentication and runtime behavior from Dify, configure the provider and run a small workflow/tool call with:

- model: `gemini-3-pro-image`
- location: `global`
- resolution: `1K`
- aspect ratio: `1:1`

If the generated response contains text but no image, the tool returns the text message instead of reporting an authentication failure.

### Unverified items

- Live Gemini Developer API and Vertex AI requests are user-side checks.
- Real credentials are user-side checks and are not inspected by the automated tests.
- Installed Dify UI workflow smoke tests are user-side checks.
- `4K` remains documented as a Pro-compatible resolution and should be included in the user's Dify workflow verification.
