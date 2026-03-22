# Krea Nano Banana 2 API (quick reference)

Endpoints (auth: `Authorization: Bearer <token>`):

- **Create job**: `POST https://api.krea.ai/generate/image/google/nano-banana-flash`
- **Poll job**: `GET https://api.krea.ai/jobs/{job_id}`

## Create job payload (JSON)

Required:
- `prompt` (string, min 3 chars)

Optional (common):
- `batchSize` (int, 1..4, default 1)
- `aspectRatio` (string) — one of: `4:1`, `21:9`, `1:1`, `4:3`, `3:2`, `2:3`, `5:4`, `4:5`, `3:4`, `16:9`, `9:16`, `1:4`, `1:8`
- `resolution` (string) — `1K` (default), `2K`, `4K`
- `width` (number) — custom width (overrides aspectRatio)
- `height` (number) — custom height (overrides aspectRatio)
- `imageUrls` (array of URI strings) — reference images for visual consistency
- `styleImages` (array of `{ url: string, strength: number (-2..2) }`) — style reference images

## Headers (optional)

- `X-Webhook-URL` (string, URI) — URL to receive POST when job completes

## Job status values

`backlogged | queued | scheduled | processing | sampling | intermediate-complete | completed | failed | cancelled`

## Completed job result

`result.urls`: array of image URLs.

## Script CLI flags

| Flag | Default | Description |
|------|---------|-------------|
| `--prompt` | (required) | Text prompt (min 3 chars) |
| `--aspect-ratio` | `1:1` | Aspect ratio |
| `--resolution` | `1K` | `1K`, `2K`, or `4K` |
| `--batch-size` | 1 | Number of images (1–4) |
| `--width` | — | Custom width (overrides aspect-ratio) |
| `--height` | — | Custom height (overrides aspect-ratio) |
| `--image-urls` | — | One or more reference image URLs (space-separated) |
| `--image-urls-json` | — | JSON array of reference image URLs |
| `--style-images-json` | — | JSON array: `[{url, strength}, ...]` |
| `--webhook-url` | — | Webhook URL for completion notification |
| `--download` | false | Download result images locally |
| `--out-dir` | `generated` | Download directory |
| `--out-prefix` | `krea_nano_banana_2` | Filename prefix |
| `--poll-interval` | 1.5 | Seconds between status polls |
| `--timeout` | 180 | Max wait in seconds |
| `--token` | — | API token (prefer env var) |
| `--quiet` | false | Suppress progress logs |

## Key differences from Z Image API

| Feature | Z Image | Nano Banana 2 |
|---------|---------|---------------|
| Endpoint | `/generate/image/z-image/z-image` | `/generate/image/google/nano-banana-flash` |
| Size control | `width` + `height` (required) | `aspectRatio` + `resolution` (or custom w/h) |
| Reference images | `imageUrl` (single) | `imageUrls` (array, multiple) |
| Init image blend | `denoising_strength` | Not supported |
| Prompt expansion | `skipPromptExpansion` | Not supported |
| Styles by ID | `styles` array | Not supported |

## URL compatibility (important)

**`imageUrls`**: Accepts Krea CDN URLs and some external URLs, but **NOT all hosts work**.
- ✅ Azure CDN (`*.azurefd.net`) — works
- ✅ Krea CDN (`app-uploads.krea.ai`) — works
- ❌ catbox.moe — silently ignored (API returns 200 but image is not used)
- ❌ Other free image hosts — untested, may be silently ignored

**`styleImages`**: Stricter validation. Only accepts Krea CDN URLs (`app-uploads.krea.ai`).
- ❌ External URLs return 422 "Invalid asset URL"

**`imageUrls` vs `styleImages`**: Mutually exclusive. API docs state: "If [imageUrls] provided, style images are ignored."

**Warning**: If `imageUrls` contains a URL that Krea cannot fetch, the API does NOT return an error — it silently ignores the reference image and generates based on prompt only. Always use a known-compatible URL host.

## Common errors

- **401** unauthenticated (token missing/invalid)
- **402** out of credits
- **429** too many concurrent jobs
- **400** invalid body (prompt too short, invalid aspect ratio, etc.)
- **422** validation failed (e.g., styleImages with non-Krea URL)
- **403 + "error code: 1010"** Cloudflare block (often fixed by setting a browser-like User-Agent)
