#!/usr/bin/env python3
"""Probe the free NVIDIA NIM models the bot depends on.

Free-tier models get retired without notice (410 EOL) — run this after any
failure and whenever GitHub starts returning "model not found". Prints one line
per model; the working ones belong in NVIDIA_MODEL / NVIDIA_FALLBACK_MODEL.

Usage:  NVIDIA_API_KEY=... python scripts/probe_nvidia.py [model ...]
"""
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_MODELS = [
    "z-ai/glm-5.3-flash",
    "openai/gpt-oss-20b",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    "nvidia/nemotron-3.5-lightning-30b-a3b",
]


def main():
    key = os.environ.get("NVIDIA_API_KEY", "").strip()
    if not key:
        print("NVIDIA_API_KEY missing")
        return 2
    models = sys.argv[1:] or DEFAULT_MODELS
    for m in models:
        body = {"model": m, "messages": [
            {"role": "system", "content": "Reply exactly: REPLY: ok"},
            {"role": "user", "content": "Comment by fan: love this shot!"}],
            "max_tokens": 200, "temperature": 0.5, "stream": False}
        req = urllib.request.Request(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            data=json.dumps(body).encode(),
            headers={"Authorization": "Bearer " + key,
                     "Content-Type": "application/json"},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                d = json.loads(r.read().decode())
            c = (d["choices"][0]["message"].get("content") or "").strip()
            verdict = "OK" if c.startswith(("REPLY:", "SKIP:", "ESCALATE:")) else "OK-but-format"
            print(f"{m}: {verdict} {c[:60]!r}")
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = json.loads(e.read().decode()).get("detail", "")
            except Exception:
                pass
            print(f"{m}: HTTP {e.code} {str(detail)[:120]}")
        except Exception as e:  # noqa: BLE001
            print(f"{m}: {type(e).__name__}: {str(e)[:120]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
