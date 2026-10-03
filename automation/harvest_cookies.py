#!/usr/bin/env python3
"""Harvest the FULL .google.com cookie jar a browser holds and print it as JSON.

The rotating chain (automation/refresh_cookies.py) needs more than SID+TS: the
RotateCookies endpoint answers 200 only when the account cookie set is present.
Run this on a machine whose browser is signed in to gemini.google.com, then:

  python3 automation/harvest_cookies.py --browser firefox > /tmp/jar.json
  gh secret set GEMINI_COOKIES_JSON -R <owner>/<repo> < /tmp/jar.json

Prints ONLY the selected cookie keys (values are secrets — do not paste them
into chats or commit them).
"""
import argparse
import json
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from refresh_cookies import JAR_KEYS  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--browser", default="firefox",
                    choices=["firefox", "chrome", "chromium", "edge"])
    args = ap.parse_args()

    import browser_cookie3 as bc3
    loader = {"firefox": bc3.firefox, "chrome": bc3.chrome,
              "chromium": bc3.chromium, "edge": bc3.edge}[args.browser]
    jar = {c.name: c.value for c in loader(domain_name="google.com")}
    picked = {k: v for k, v in jar.items() if k in JAR_KEYS and v}
    if "__Secure-1PSID" not in picked:
        print(json.dumps({"ok": False, "err": "no signed-in google cookies in "
                                              f"{args.browser}"}))
        return 2
    sys.stderr.write(f"{args.browser}: {len(jar)} google cookies, kept "
                     f"{len(picked)}: {sorted(picked)}\n")
    print(json.dumps(picked))
    return 0


if __name__ == "__main__":
    sys.exit(main())
