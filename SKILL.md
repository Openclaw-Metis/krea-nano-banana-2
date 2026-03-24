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

### 3) Reference images — identity preservation

Use `--image-urls` when the goal is **same face / same identity** across different scenes.

#### Identity vs style

| Goal | Flag | Preserves |
|------|------|-----------|
| Same face in new scene | `--image-urls` | Identity |
| Same aesthetic / palette | `--style-images-json` | Style only |

`imageUrls` and `styleImages` are mutually exclusive. When both are present, the API uses `imageUrls`.

#### Prompt rules for identity lock

Reference owns the face. Prompt owns scene, wardrobe, lighting, mood, and composition.

Include: scene, environment, wardrobe, lighting, mood, composition, short subject anchor.
Leave out: facial features, ethnicity, skin tone, age markers, hair details that already exist in the reference.

Golden template:
```
[subject anchor], [wardrobe], [action/pose], [environment], [lighting/mood], [photography style], [quality]
```
`"a young woman, oversized denim jacket, leaning on a railing, rooftop bar overlooking city skyline at dusk, warm golden light, lifestyle photography, 8k"`

Rules:
1. Keep the subject anchor short and identical across a series.
2. Generate one identity per image. Put bystanders in background blur only.
3. Use 1-2 clear, front-facing reference photos. More refs soften features.
4. Keep the face unobstructed. Avoid sunglasses, masks, large hats, heavy bangs.

#### Identity-locked prompt examples

Café, 4:5
`"a young woman, white linen shirt, sitting at an outdoor café table, croissant and espresso, morning sunlight, lifestyle photography, 8k"`

Urban night, 4:5
`"a young woman walking through neon-lit Shibuya crossing at night, black leather jacket, street photography, cinematic, rain-wet reflections"`

Fantasy / armor, 4:5
`"a young woman in silver armor standing in a snow-covered forest clearing, breath visible in cold air, overcast diffused light, epic fantasy photography, 8k"`

#### Multi-scene series

Lock these across the whole series:
- same `--image-urls`
- same subject anchor text
- same `--resolution`
- same `--aspect-ratio`

Vary only scene, wardrobe, lighting, composition, and action. Generate one image at a time (`--batch-size 1`). Before the next image, compare the result with the reference. If facial structure, skin tone, or age drift, fix the prompt first.

#### Failure modes

| Symptom | Fix |
|---------|-----|
| Face changes between scenes | Remove facial descriptors. Let the reference own the face. |
| Reference silently ignored | Use Azure CDN or Krea CDN. Test the first output before committing to a series. |
| Identity averages out | Use 1-2 refs max, front-facing, well-lit. |
| Attribute drift | Do not restate ethnicity, skin tone, age, or hair details unless you want them changed. |
| Series inconsistency | Keep anchor text, aspect ratio, and resolution identical across the series. |
| Face hallucinated | Do not occlude the face with sunglasses, masks, large hats, or heavy bangs. |

#### URL compatibility

Reliable: Azure CDN (`*.azurefd.net`), Krea CDN (`app-uploads.krea.ai`).
Broken: catbox.moe.
Other hosts: test first.

Krea may return success even when the reference URL was ignored. If the first output looks generic, treat the URL as untrusted and retry with a supported host.

See `references/nano-banana-2-api.md` for full API details.

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
