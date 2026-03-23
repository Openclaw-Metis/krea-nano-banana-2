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
  Export KREA_API_KEY / KREA_API_KEY_2 / KREA_API_KEY_3 (or KREA_TOKEN*)
  or pass --token.
  If neither is set, this script will also try to load token candidates from the
  local OpenClaw config (~/.openclaw/openclaw.json) under:
    skills.entries.krea-nano-banana-2.env.KREA_API_KEY
    skills.entries.krea-nano-banana-2.env.KREA_API_KEY_2
    skills.entries.krea-nano-banana-2.env.KREA_API_KEY_3

  When job creation returns INSUFFICIENT_BALANCE (HTTP 402), the script
  automatically retries with the next configured token.

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
from typing import Any, Dict, Iterable, List, Optional, Tuple

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


def _dedupe_keep_order(values: Iterable[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for value in values:
        v = str(value).strip()
        if not v or v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out



def _extract_token_candidates(env: Dict[str, Any]) -> List[str]:
    candidates: List[str] = []
    for base in ("KREA_API_KEY", "KREA_TOKEN"):
        primary = env.get(base)
        if primary:
            candidates.append(str(primary))

        numbered: List[Tuple[int, str]] = []
        prefix = f"{base}_"
        for key, value in env.items():
            if not value or not key.startswith(prefix):
                continue
            suffix = key[len(prefix):]
            if suffix.isdigit():
                numbered.append((int(suffix), str(value)))
        for _, value in sorted(numbered, key=lambda x: x[0]):
            candidates.append(value)

    return _dedupe_keep_order(candidates)



def _tokens_from_openclaw_config(skill_name: str = "krea-nano-banana-2", quiet: bool = False) -> List[str]:
    """Best-effort token lookup from the local OpenClaw config."""
    cfg_path = os.environ.get("OPENCLAW_CONFIG") or os.path.expanduser("~/.openclaw/openclaw.json")
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except FileNotFoundError:
        return []
    except Exception as e:
        if not quiet:
            _eprint(f"Warning: failed to read OpenClaw config at {cfg_path}: {e}")
        return []

    try:
        tokens: List[str] = []
        for name in (skill_name, "krea-z-image"):
            env = (
                (((cfg.get("skills") or {}).get("entries") or {}).get(name) or {}).get("env")
                or {}
            )
            tokens.extend(_extract_token_candidates(env))
        return _dedupe_keep_order(tokens)
    except Exception:
        return []


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


class KreaHttpError(RuntimeError):
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self.payload = payload
        super().__init__(f"HTTP {status_code}: {json.dumps(payload, ensure_ascii=False)}")



def _extract_krea_error_code(payload: dict) -> Optional[str]:
    candidates = [
        payload.get("code"),
        payload.get("error_code"),
        (payload.get("error") or {}).get("code") if isinstance(payload.get("error"), dict) else None,
    ]
    for value in candidates:
        if value:
            return str(value)
    return None



def _extract_krea_error_message(payload: dict) -> Optional[str]:
    candidates = [
        payload.get("message"),
        payload.get("error"),
        payload.get("detail"),
        (payload.get("error") or {}).get("message") if isinstance(payload.get("error"), dict) else None,
    ]
    for value in candidates:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None



def _format_krea_error(err: Exception) -> str:
    if not isinstance(err, KreaHttpError):
        return str(err)
    code = _extract_krea_error_code(err.payload)
    message = _extract_krea_error_message(err.payload)
    parts = [f"HTTP {err.status_code}"]
    if code:
        parts.append(code)
    if message:
        parts.append(message)
    return ": ".join([parts[0], " - ".join(parts[1:])]) if len(parts) > 1 else parts[0]



def _is_insufficient_balance_error(err: Exception) -> bool:
    if not isinstance(err, KreaHttpError) or err.status_code != 402:
        return False
    raw_text = json.dumps(err.payload, ensure_ascii=False).lower()
    return "insufficient_balance" in raw_text or "insufficient balance" in raw_text



def _format_job_create_failure(err: Exception, token_count: int) -> str:
    if _is_insufficient_balance_error(err):
        if token_count > 1:
            return f"All {token_count} configured Krea tokens returned INSUFFICIENT_BALANCE (HTTP 402)."
        return "Configured Krea token returned INSUFFICIENT_BALANCE (HTTP 402)."
    return f"Failed to create Krea job after trying {token_count} token(s): {_format_krea_error(err)}"



def http_json(method: str, path: str, token: str, user_agent: str,
              body: Optional[dict] = None, webhook_url: Optional[str] = None) -> dict:
    url = f"{API_BASE}{path}"
    headers = _headers(token, user_agent, webhook_url)

    code, j = _urllib_json(method, url, headers, body)

    if code in (401, 402, 400, 404, 429):
        raise KreaHttpError(code, j)
    if code == 403:
        raw_text = json.dumps(j, ensure_ascii=False).lower()
        if "1010" in raw_text or "access denied" in raw_text:
            code2, j2 = _curl_json(method, url, headers, body)
            if code2 in (401, 402, 400, 404, 429, 403):
                raise KreaHttpError(code2, j2)
            return j2
        raise KreaHttpError(403, j)
    if code >= 400:
        raise KreaHttpError(code, j)
    return j



def create_job_with_token_fallback(path: str, tokens: List[str], user_agent: str,
                                   body: Optional[dict] = None, webhook_url: Optional[str] = None,
                                   quiet: bool = False) -> Tuple[dict, str]:
    last_error: Optional[Exception] = None
    for idx, token in enumerate(tokens, start=1):
        try:
            if len(tokens) > 1 and not quiet:
                _eprint(f"create_job: trying Krea token {idx}/{len(tokens)}")
            return http_json("POST", path, token, user_agent, body, webhook_url=webhook_url), token
        except Exception as err:
            last_error = err
            if _is_insufficient_balance_error(err) and idx < len(tokens):
                if not quiet:
                    _eprint(f"create_job: token {idx}/{len(tokens)} has insufficient balance, switching to token {idx + 1}/{len(tokens)}")
                continue
            raise
    assert last_error is not None
    raise last_error


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

    token_candidates = _dedupe_keep_order(
        ([args.token] if args.token else [])
        + _extract_token_candidates(dict(os.environ))
        + _tokens_from_openclaw_config(quiet=args.quiet)
    )
    if token_candidates and not args.quiet:
        source = "argument/env/config" if args.token else "env/config"
        _eprint(f"Loaded {len(token_candidates)} Krea token candidate(s) from {source}.")

    if not token_candidates:
        raise SystemExit(
            "Missing token. Provide --token, set KREA_API_KEY / KREA_TOKEN (optionally KREA_API_KEY_2, KREA_API_KEY_3), "
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

    try:
        job, token = create_job_with_token_fallback(
            GENERATE_PATH,
            token_candidates,
            args.user_agent,
            body,
            webhook_url=args.webhook_url,
            quiet=args.quiet,
        )
    except Exception as e:
        raise SystemExit(_format_job_create_failure(e, len(token_candidates)))
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
