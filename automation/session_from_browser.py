#!/usr/bin/env python3
"""Build an instagrapi session from a browser that is already logged in.

Why: password logins and stolen/expired session dumps get challenged. If the
Instagram account is logged in inside Firefox/Chrome on this machine, the
`sessionid` cookie is a legitimate, current credential — this script turns it
into an instagrapi session and verifies it.

Usage:
  python automation/session_from_browser.py                    # firefox, verify
  python automation/session_from_browser.py --browser chrome
  python automation/session_from_browser.py --out /tmp/s.json --test-write

Then store it as a repository secret:
  gh secret set IG_SESSION_JSON -R <owner>/<repo> < automation/.session.json

Notes:
  * requires browser_cookie3 (pip install browser_cookie3)
  * --test-write like/unlikes your own newest post (instant undo) to prove the
    machine's egress IP is allowed to write — the thing datacenter IPs fail.
  * the session is written with mode 600 and is git-ignored.
"""
import argparse
import os
import sys
import time

from instagrapi import Client

UUIDS = {
    "phone_id": "e6b4c29d-6908-435f-88ec-3bd9e17e8760",
    "uuid": "a3f1bdc7-41ee-4a4a-8c8b-4da97d54dddf",
    "client_session_id": "3481c650-7351-43d5-a963-2a4e3302f87d",
    "advertising_id": "973443aa-5f0c-4d46-a373-063813d4c0f7",
    "android_device_id": "android-409c26a6b623b92b",
    "request_id": "bb2d0c55-b1f2-4444-b5db-040b57a22cce",
    "tray_session_id": "c14b1c76-c0cf-4f38-ab1f-e09a775d00ce",
}


def harvest(browser):
    import browser_cookie3 as bc3
    loader = {"firefox": bc3.firefox, "chrome": bc3.chrome,
              "chromium": bc3.chromium, "edge": bc3.edge}[browser]
    jar = loader(domain_name="instagram.com")
    return {c.name: c.value for c in jar if "instagram.com" in (c.domain or "")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--browser", default="firefox",
                    choices=["firefox", "chrome", "chromium", "edge"])
    ap.add_argument("--out", default="automation/.session.json")
    ap.add_argument("--test-write", action="store_true",
                    help="like/unlike the newest own post to prove write access")
    args = ap.parse_args()

    cookies = harvest(args.browser)
    sid = cookies.get("sessionid")
    print(f"{args.browser}: {len(cookies)} instagram cookies, "
          f"sessionid={'yes' if sid else 'NO'}")
    if not sid:
        print("Log in to instagram.com in that browser first (the cookie is what we need).")
        return 2

    cl = Client(settings={"uuids": dict(UUIDS)})
    cl.delay_range = [1, 3]
    t0 = time.time()
    cl.login_by_sessionid(sid)
    print(f"login_by_sessionid OK ({time.time() - t0:.1f}s) "
          f"user_id={cl.user_id} username={cl.username}")

    try:
        me = cl.account_info()
        print(f"verified: @{me.username} (pk {me.pk})")
    except Exception as e:  # noqa: BLE001
        print(f"verification call failed: {type(e).__name__}: {str(e)[:140]}")
        print("The session may still be usable — check with automation/ig_probe.py")

    if args.test_write:
        try:
            pk = cl.user_medias(cl.user_id, 1)[0].pk
            cl.media_like(pk)
            cl.media_unlike(pk)
            print("write test OK (liked + unliked the newest post)")
        except Exception as e:  # noqa: BLE001
            print(f"write test FAILED: {type(e).__name__}: {str(e)[:140]}")
            print("→ this machine's IP cannot write to Instagram; run the bot on a "
                  "residential connection (see AGENTS.md)")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    cl.dump_settings(args.out)
    os.chmod(args.out, 0o600)
    print(f"session written to {args.out} (mode 600, git-ignored)")
    print("store it as a secret with:")
    print(f"  gh secret set IG_SESSION_JSON -R <owner>/<repo> < {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
