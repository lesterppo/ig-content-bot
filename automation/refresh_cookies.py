#!/usr/bin/env python3
"""Keep web-Gemini cookies alive inside CI — no browser, no local machine.

Why this exists
---------------
Google rotates ``__Secure-1PSIDTS`` server-side; an old value stops
authenticating and image generation dies with ``Auth expired``. The endpoint
``accounts.google.com/RotateCookies`` hands out a fresh ``__Secure-1PSIDTS``
when it is called with the *full* ``.google.com`` cookie jar (SID plus the
account cookies) — see the repo docs. This script turns that into a
self-refreshing chain:

  1. gather candidate cookie pairs, newest first:
       browser (self-hosted only) -> cached jar -> GEMINI_COOKIES_JSON -> env
  2. probe each with the vendored CLI (``--account-status``); first AVAILABLE wins
  3. if none authenticates, rotate ``__Secure-1PSIDTS`` on each full jar
     available and probe the result
  4. write the winning jar to ``--out`` (the workflow caches it, so the next run
     starts from the newest link) and, with ``--emit-env``, export
     GEMINI_SID/GEMINI_TS into ``$GITHUB_ENV`` for later steps

Exit codes: 0 ok, 3 the anchor is dead (a human must re-harvest cookies from a
signed-in browser).

Never prints cookie values.
"""
import argparse
import json
import os
import subprocess
import sys

ROTATE_URL = "https://accounts.google.com/RotateCookies"
ROTATE_BODY = '[000,"-0000000000000000000"]'
HERE = os.path.dirname(os.path.abspath(__file__))
CLI = os.environ.get("GEMINI_CLI") or os.path.join(HERE, "gemini-cli.py")

JAR_KEYS = ("__Secure-1PSID", "__Secure-1PSIDTS", "SID", "HSID", "SSID", "APISID",
            "SAPISID", "__Secure-1PAPISID", "__Secure-3PSID", "__Secure-3PAPISID",
            "LSID", "NID", "AEC", "__Secure-1PSIDCC", "__Secure-3PSIDCC",
            "ACCOUNT_CHOOSER", "SIDCC", "OSID", "T", "GAPS")


def log(msg):
    print(msg, flush=True)


def probe(sid, ts, timeout=180):
    """Cheap live check through the vendored CLI. Returns status_name or None."""
    env = dict(os.environ, GEMINI_SID=sid, GEMINI_TS=ts or "")
    try:
        r = subprocess.run([sys.executable, CLI, "--account-status"],
                           capture_output=True, text=True, timeout=timeout,
                           env=env, cwd=HERE)
    except subprocess.TimeoutExpired:
        return None
    for line in reversed(r.stdout.splitlines()):
        if line.startswith("{"):
            try:
                return json.loads(line).get("status_name")
            except json.JSONDecodeError:
                return None
    return None


def rotate(jar):
    """Ask Google for a fresh __Secure-1PSIDTS. Returns (status, new_ts)."""
    try:
        from curl_cffi import requests as creq
    except ImportError:
        log("  curl_cffi missing; cannot rotate")
        return None, None
    s = creq.Session(impersonate="chrome")
    for k, v in jar.items():
        if v:
            s.cookies.set(k, v, domain=".google.com")
    try:
        r = s.post(ROTATE_URL, data=ROTATE_BODY,
                   headers={"Content-Type": "application/json",
                            "Origin": "https://accounts.google.com",
                            "Referer": "https://accounts.google.com/"},
                   timeout=30)
    except Exception as e:  # noqa: BLE001
        log(f"  rotate failed: {type(e).__name__}: {str(e)[:120]}")
        return None, None
    new_ts = s.cookies.get("__Secure-1PSIDTS")
    return r.status_code, new_ts


def browser_jar():
    try:
        import browser_cookie3 as bc3
    except ImportError:
        return None
    for name, loader in (("firefox", bc3.firefox), ("chrome", bc3.chrome),
                         ("chromium", bc3.chromium)):
        try:
            jar = {c.name: c.value for c in loader(domain_name="google.com")}
        except Exception:  # noqa: BLE001
            continue
        if jar.get("__Secure-1PSID"):
            log(f"  browser:{name} has a signed-in jar")
            return jar
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=".gemini_cookies.json",
                    help="where to store the winning jar (cached by the workflow)")
    ap.add_argument("--emit-env", action="store_true",
                    help="append GEMINI_SID/GEMINI_TS to $GITHUB_ENV")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--skip-rotate", action="store_true")
    args = ap.parse_args()

    candidates = []  # (source, sid, ts, jar)

    if not args.no_browser:
        jar = browser_jar()
        if jar:
            candidates.append(("browser", jar["__Secure-1PSID"],
                               jar.get("__Secure-1PSIDTS"), jar))

    if os.path.exists(args.out):
        try:
            jar = json.load(open(args.out))
            if jar.get("__Secure-1PSID"):
                candidates.append(("cache", jar["__Secure-1PSID"],
                                   jar.get("__Secure-1PSIDTS"), jar))
        except (OSError, json.JSONDecodeError):
            pass

    raw = os.environ.get("GEMINI_COOKIES_JSON", "")
    if raw:
        try:
            jar = json.loads(raw)
            if jar.get("__Secure-1PSID"):
                candidates.append(("secret-jar", jar["__Secure-1PSID"],
                                   jar.get("__Secure-1PSIDTS"), jar))
        except json.JSONDecodeError:
            log("  GEMINI_COOKIES_JSON is not valid JSON")

    if os.environ.get("GEMINI_SID"):
        candidates.append(("env", os.environ["GEMINI_SID"],
                           os.environ.get("GEMINI_TS"), None))

    if not candidates:
        log("no cookie candidates at all (set GEMINI_COOKIES_JSON or run on a "
            "machine with a signed-in browser)")
        return 3

    winner = None
    for src, sid, ts, jar in candidates:
        st = probe(sid, ts)
        log(f"  [{src}] status={st}")
        if st == "AVAILABLE":
            winner = (src, sid, ts, jar)
            break

    if not winner and not args.skip_rotate:
        # rotation needs a full jar; the plain SID/TS pair is not enough
        for src, sid, ts, jar in candidates:
            if not jar:
                continue
            code, new_ts = rotate(jar)
            log(f"  [rotate:{src}] HTTP {code}")
            if code == 200 and new_ts:
                new_jar = dict(jar)
                new_jar["__Secure-1PSIDTS"] = new_ts
                st = probe(sid, new_ts)
                log(f"  [rotate:{src}] status={st}")
                if st == "AVAILABLE":
                    winner = (f"rotate:{src}", sid, new_ts, new_jar)
                    break

    if not winner:
        log("::warning::no cookie set authenticates and rotation did not rescue it — "
            "the anchor is dead. Re-harvest cookies from a signed-in browser "
            "(automation/gemini-cli.py --init --browser firefox) and update the "
            "GEMINI_COOKIES_JSON / GEMINI_SID / GEMINI_TS secrets.")
        return 3

    src, sid, ts, jar = winner
    out_jar = dict(jar or {})
    out_jar.update({"__Secure-1PSID": sid, "__Secure-1PSIDTS": ts,
                    "_source": src, "_saved": __import__("time").strftime(
                        "%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime())})
    # keep the file small: only the cookie keys that matter
    out_jar = {k: v for k, v in out_jar.items()
               if k in JAR_KEYS or k.startswith("_")}
    with open(args.out, "w") as f:
        json.dump(out_jar, f)
    log(f"winner: {src}; jar written to {args.out} "
        f"({len(out_jar)} keys, sid…{sid[-6:]})")

    if args.emit_env:
        gh_env = os.environ.get("GITHUB_ENV")
        if gh_env:
            with open(gh_env, "a") as f:
                f.write(f"GEMINI_SID={sid}\nGEMINI_TS={ts}\n")
            log("exported GEMINI_SID/GEMINI_TS to $GITHUB_ENV")
        else:
            log("no $GITHUB_ENV (not running inside a workflow) — values not exported")
    return 0


if __name__ == "__main__":
    sys.exit(main())
