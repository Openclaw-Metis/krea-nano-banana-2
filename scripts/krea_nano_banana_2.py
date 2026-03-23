#!/usr/bin/env python3
"""Generate images via Krea Nano Banana 2 (Google Imagen).

- Creates a job: POST /generate/image/google/nano-banana-flash
- Polls job: GET /jobs/{id}
- Optionally downloads result URLs to local files

Prints a single JSON object to stdout:
{
  "job_id": "...",
  "status": "completed",
  "urls": ["..."],
  "files": ["/abs/or/rel/path.png"],
  "aspect_ratio": "4:5",
  "resolution": "1K"
}

Auth:
  Export KREA_API_KEY (or KREA_TOKEN) or pass --token.
  If neither is set, this script will also try to load the token from the
  local OpenClaw config (~/.openclaw/openclaw.json) under:
    skills.entries.krea-nano-banana-2.env.KREA_API_KEY

Note: Calls consume Krea credits.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

API_BASE = "https://api.krea.ai"
GENERATE_PATH = "/generate/image/google/nano-banana-flash"
DEFAULT_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)

VALID_ASPECT_RATIOS = [
    "4:1", "21:9", "1:1", "4:3", "3:2", "2:3",
    "5:4", "4:5", "3:4", "16:9", "9:16", "1:4", "1:8",
]
VALID_RESOLUTIONS = ["1K", "2K", "4K"]


def _eprint(*a: Any) -> None:
    print(*a, file=sys.stderr)


def _headers(token: str, user_agent: str, webhook_url: Optional[str] = None) -> Dict[str, str]:
    h = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": user_agent,
        "Accept-Language": "en-US,en;q=0.9",
    }
    if webhook_url:
        h["X-Webhook-URL"] = webhook_url
    return h


def _token_from_openclaw_config(skill_name: str = "krea-nano-banana-2", quiet: bool = False) -> Optional[str]:
    """Best-effort token lookup from the local OpenClaw config."""
    cfg_path = os.environ.get("OPENCLAW_CONFIG") or os.path.expanduser("~/.openclaw/openclaw.json")
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except FileNotFoundError:
        return None
    except Exception as e:
        if not quiet:
            _eprint(f"Warning: failed to read OpenClaw config at {cfg_path}: {e}")
        return None

    try:
        # Try skill-specific config first, then fall back to krea-z-image config
        for name in (skill_name, "krea-z-image"):
            env = (
                (((cfg.get("skills") or {}).get("entries") or {}).get(name) or {}).get("env")
                or {}
            )
            tok = env.get("KREA_API_KEY") or env.get("KREA_TOKEN")
            if tok:
                return str(tok)
        return None
    except Exception:
        return None


def _urllib_json(method: str, url: str, headers: Dict[str, str], body: Optional[dict]) -> Tuple[int, dict]:
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            if not raw:
                return resp.status, {}
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, {"raw": raw}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            j = json.loads(raw) if raw else {"error": e.reason}
        except json.JSONDecodeError:
            j = {"error": raw or str(e)}
        return e.code, j


def _curl_json(method: str, url: str, headers: Dict[str, str], body: Optional[dict]) -> Tuple[int, dict]:
    cmd = ["curl", "-sS", "-X", method]
    for k, v in headers.items():
        cmd += ["-H", f"{k}: {v}"]
    if body is not None:
        cmd += ["--data", json.dumps(body, ensure_ascii=False)]
    cmd += ["-w", "\n%{http_code}", url]

    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out = p.stdout
    if not out:
        return 0, {"error": p.stderr.strip() or "empty response"}

    if "\n" not in out:
        return 0, {"error": out}
    body_txt, code_txt = out.rsplit("\n", 1)
    try:
        code = int(code_txt.strip())
    except ValueError:
        code = 0
    try:
        j = json.loads(body_txt) if body_txt else {}
    except json.JSONDecodeError:
        j = {"raw": body_txt}
    if p.returncode != 0 and "error" not in j:
        j["error"] = p.stderr.strip()
    return code, j


def http_json(method: str, path: str, token: str, user_agent: str,
              body: Optional[dict] = None, webhook_url: Optional[str] = None) -> dict:
    url = f"{API_BASE}{path}"
    headers = _headers(token, user_agent, webhook_url)

    code, j = _urllib_json(method, url, headers, body)

    if code in (401, 402, 400, 404, 429):
        raise RuntimeError(f"HTTP {code}: {json.dumps(j, ensure_ascii=False)}")
    if code == 403:
        raw_text = json.dumps(j, ensure_ascii=False).lower()
        if "1010" in raw_text or "access denied" in raw_text:
            code2, j2 = _curl_json(method, url, headers, body)
            if code2 in (401, 402, 400, 404, 429, 403):
                raise RuntimeError(f"HTTP {code2}: {json.dumps(j2, ensure_ascii=False)}")
            return j2
        raise RuntimeError(f"HTTP 403: {json.dumps(j, ensure_ascii=False)}")
    if code >= 400:
        raise RuntimeError(f"HTTP {code}: {json.dumps(j, ensure_ascii=False)}")
    return j


def download(url: str, out_path: pathlib.Path, user_agent: str) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            out_path.write_bytes(resp.read())
    except Exception:
        cmd = ["curl", "-L", "--fail", "-sS", "-H", f"User-Agent: {user_agent}", "-o", str(out_path), url]
        subprocess.run(cmd, check=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate images via Krea Nano Banana 2 API and optionally download results.")
    ap.add_argument("--prompt", required=True, help="Text prompt (min 3 chars)")
    ap.add_argument("--aspect-ratio", default="1:1", choices=VALID_ASPECT_RATIOS,
                     help="Aspect ratio (default: 1:1)")
    ap.add_argument("--resolution", default="1K", choices=VALID_RESOLUTIONS,
                     help="Resolution: 1K, 2K, or 4K (default: 1K)")
    ap.add_argument("--batch-size", type=int, default=1, help="1-4 images per job")
    ap.add_argument("--width", type=int, help="Custom width (overrides aspect-ratio)")
    ap.add_argument("--height", type=int, help="Custom height (overrides aspect-ratio)")

    ap.add_argument("--image-urls", nargs="+", help="Reference image URL(s) for consistency")
    ap.add_argument("--image-urls-json", help="JSON array of reference image URLs")
    ap.add_argument("--style-images-json", help='JSON array: [{"url": "...", "strength": 1.0}, ...]')

    ap.add_argument("--webhook-url", help="URL to receive POST when job completes")

    ap.add_argument("--token", help="Krea API token (prefer env KREA_API_KEY)")
    ap.add_argument("--user-agent", default=DEFAULT_UA)

    ap.add_argument("--poll-interval", type=float, default=1.5)
    ap.add_argument("--timeout", type=float, default=180)

    ap.add_argument("--download", action="store_true", help="Download completed image(s)")
    ap.add_argument("--out-dir", default="generated", help="Output directory for downloads")
    ap.add_argument("--out-prefix", default="krea_nano_banana_2", help="Filename prefix")

    ap.add_argument("--quiet", action="store_true", help="Suppress progress logs")

    args = ap.parse_args()

    if len(args.prompt) < 3:
        raise SystemExit("--prompt must be at least 3 characters")
    if not (1 <= args.batch_size <= 4):
        raise SystemExit("--batch-size must be 1..4")

    token = args.token or os.environ.get("KREA_API_KEY") or os.environ.get("KREA_TOKEN")
    if not token:
        token = _token_from_openclaw_config(quiet=args.quiet)
        if token and not args.quiet:
            _eprint("Loaded Krea token from OpenClaw config (~/.openclaw/openclaw.json).")

    if not token:
        raise SystemExit(
            "Missing token. Provide --token, set KREA_API_KEY / KREA_TOKEN, "
            "or configure OpenClaw skill env (skills.entries.krea-nano-banana-2.env.KREA_API_KEY)."
        )

    body: Dict[str, Any] = {
        "prompt": args.prompt,
        "batchSize": args.batch_size,
        "aspectRatio": args.aspect_ratio,
        "resolution": args.resolution,
    }

    # Custom width/height override aspectRatio
    if args.width:
        body["width"] = args.width
    if args.height:
        body["height"] = args.height

    # Reference images (imageUrls)
    image_urls: List[str] = []
    if args.image_urls:
        image_urls = args.image_urls
    elif args.image_urls_json:
        try:
            image_urls = json.loads(args.image_urls_json)
        except json.JSONDecodeError as e:
            raise SystemExit(f"--image-urls-json is not valid JSON: {e}")
    if image_urls:
        body["imageUrls"] = image_urls

    # Style images
    style_images = None
    if args.style_images_json:
        try:
            style_images = json.loads(args.style_images_json)
        except json.JSONDecodeError as e:
            raise SystemExit(f"--style-images-json is not valid JSON: {e}")

    # imageUrls and styleImages are mutually exclusive
    if image_urls and style_images:
        raise SystemExit("Cannot use both --image-urls and --style-images-json. "
                         "The API ignores styleImages when imageUrls is present.")
    if style_images:
        body["styleImages"] = style_images

    job = http_json("POST", GENERATE_PATH, token, args.user_agent, body,
                    webhook_url=args.webhook_url)
    job_id = job.get("job_id")
    if not job_id:
        raise SystemExit(f"No job_id in response: {json.dumps(job, ensure_ascii=False)}")

    t0 = time.time()
    last_status = job.get("status")
    if not args.quiet:
        _eprint(f"job_id={job_id} status={last_status}")

    final: dict = {}
    while True:
        if time.time() - t0 > args.timeout:
            raise SystemExit(f"Timed out after {args.timeout}s waiting for job completion (job_id={job_id}).")

        j = http_json("GET", f"/jobs/{job_id}", token, args.user_agent)
        status = j.get("status")

        if status != last_status and not args.quiet:
            _eprint(f"status={status}")
            last_status = status

        if status in ("completed", "failed", "cancelled"):
            final = j
            break

        time.sleep(args.poll_interval)

    if final.get("status") != "completed":
        raise SystemExit(json.dumps(final, ensure_ascii=False))

    urls: List[str] = (final.get("result") or {}).get("urls") or []
    out_files: List[str] = []

    if args.download and urls:
        out_dir = pathlib.Path(args.out_dir)
        for idx, u in enumerate(urls, start=1):
            ext = pathlib.Path(u.split("?", 1)[0]).suffix or ".png"
            out_path = out_dir / f"{args.out_prefix}_{job_id}_{idx}{ext}"
            download(u, out_path, args.user_agent)
            out_files.append(str(out_path))

    result = {
        "job_id": job_id,
        "status": "completed",
        "urls": urls,
        "files": out_files,
        "aspect_ratio": args.aspect_ratio,
        "resolution": args.resolution,
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
