---
name: krea-nano-banana-2
description: "Generate images using the Krea Nano Banana 2 (Google Imagen) API. Use when the user asks to generate images with Nano Banana, Banana 2, or Krea Imagen — 觸發: 'nano banana', 'banana 2 生圖', '用 nano banana 出圖', '用 krea banana 畫', 'krea nano banana', '幫我用 nano banana 生成圖片', 'imagen'. Not for editing existing images, non-Krea generation, image analysis, or general 'generate an image' without mentioning Nano Banana/Banana 2. Output: image URL(s) in chat + downloaded file(s) attached inline."
---

# Krea Nano Banana 2

## Quick start

```bash
python3 {baseDir}/scripts/krea_nano_banana_2.py \
  --prompt "a young woman walking through a neon-lit Tokyo street at night, K-pop style, photorealistic" \
  --aspect-ratio 4:5 \
  --download --out-dir generated
```

The script creates a job, polls until done, optionally downloads. Stdout is a single JSON: `{ job_id, status, urls, files, aspect_ratio, resolution }`.

## Auth

Never echo the Krea token back to the user.

Token resolution (in order):
1. `--token` CLI flag
2. `KREA_API_KEY` or `KREA_TOKEN` env var
3. OpenClaw config: `~/.openclaw/openclaw.json` → `skills.entries.krea-nano-banana-2.env.KREA_API_KEY`

For persistent deployments, inject the env var via systemd drop-in or equivalent. If a user pastes a token directly, recommend they rotate it afterward.

## Workflow

### 1) Build the prompt

Write a descriptive English prompt — subject, style, lighting, composition. See `references/prompt-guide.md`.

### 2) Pick aspect ratio and resolution

Nano Banana 2 uses aspect ratio (not width/height). Common presets:

| Aspect Ratio | Use Case |
|-------------|----------|
| 1:1 | IG feed square |
| 4:5 | IG feed portrait (recommended) |
| 9:16 | IG stories / reels |
| 3:4 | Portrait |
| 16:9 | Landscape / banner |
| 3:2 | Classic photo |

Resolution: `1K` (default), `2K`, or `4K`.

Batch: 1–4 images (default 1). More images = more credits.

### 3) Reference images (optional, for character consistency)

To maintain the same face/character across scenes, pass `--image-urls` with 1-3 reference image URLs:

```bash
python3 {baseDir}/scripts/krea_nano_banana_2.py \
  --prompt "..." \
  --aspect-ratio 4:5 \
  --image-urls "https://example.azurefd.net/ref.png" \
  --download --out-dir generated
```

**URL compatibility warning:**
- Azure CDN (`*.azurefd.net`) and Krea CDN (`app-uploads.krea.ai`) — work
- catbox.moe — silently ignored (API returns 200 but reference is not used)
- Other external URLs — may work, try first
- `imageUrls` and `styleImages` are **mutually exclusive** (API ignores styleImages when imageUrls is present)

See `references/nano-banana-2-api.md` for full details on `styleImages`, webhooks, and all CLI flags.

### 4) Run the script

```bash
python3 {baseDir}/scripts/krea_nano_banana_2.py \
  --prompt "..." \
  --aspect-ratio 4:5 \
  --resolution 2K \
  --download --out-dir generated
```

Always pass `--download`.

### 5) Present the result — follow the output contract below.

## Output contract

When the script completes, always do **both**:

1. **Show the URL(s)** in your text response so the user can open them in a browser.
2. **Attach the downloaded file(s)** so the image renders inline in chat.

Attach the local file inline (via Discord reply `files`, or by referencing the path in chat). If the current surface does not support file attachments, fall back to URL-only and tell the user.

Required response format:

```
Image generated successfully.
- Aspect ratio: {aspect_ratio}
- Resolution: {resolution}
- URL: https://...
[attached: generated/krea_nano_banana_2_{job_id}_1.png]
```

Never omit the URL. Never skip attachment when local files are available.

## Error handling

If the script fails, consult `references/error-handling.md`. Common issues: expired token (401), insufficient credits (402), Cloudflare block (403/1010), rate limit (429).

## References

- `references/nano-banana-2-api.md` — API fields, all CLI flags, job statuses
- `references/prompt-guide.md` — prompt writing tips and examples
- `references/error-handling.md` — error codes, retry logic, polling behavior
