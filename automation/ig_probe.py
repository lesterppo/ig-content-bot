#!/usr/bin/env python3
"""Diagnose which Instagram surfaces a runner can reach with the stored session.

Read-only: loads IG_SESSION_JSON and tries each API surface the bot depends on,
reporting timings and exact errors. Never posts, never replies, never logs in
with the password (so it cannot trigger a challenge).

Prints one line per probe:
  [label] OK (2.1s) -> ...
  [label] FAIL (2.1s) ClientThrottledError: ...
"""
import json
import os
import sys
import time

from instagrapi import Client


def step(label, fn):
    t0 = time.time()
    try:
        r = fn()
        print(f"[{label}] OK ({time.time() - t0:.1f}s) -> {str(r)[:140]}")
        return r
    except Exception as e:  # noqa: BLE001 - diagnostic
        print(f"[{label}] FAIL ({time.time() - t0:.1f}s) "
              f"{type(e).__name__}: {str(e)[:200]}")
        return None


def main():
    username = os.environ.get("IG_USERNAME", "")
    session_json = os.environ.get("IG_SESSION_JSON", "")
    if not session_json:
        print("no IG_SESSION_JSON")
        return 1

    cl = Client(settings={"uuids": {
        "phone_id": "e6b4c29d-6908-435f-88ec-3bd9e17e8760",
        "uuid": "a3f1bdc7-41ee-4a4a-8c8b-4da97d54dddf",
        "client_session_id": "3481c650-7351-43d5-a963-2a4e3302f87d",
        "advertising_id": "973443aa-5f0c-4d46-a373-063813d4c0f7",
        "android_device_id": "android-409c26a6b623b92b",
        "request_id": "bb2d0c55-b1f2-4444-b5db-040b57a22cce",
        "tray_session_id": "c14b1c76-c0cf-4f38-ab1f-e09a775d00ce",
    }})
    cl.delay_range = [1, 2]
    cl.set_settings(json.loads(session_json))
    cl.username = username
    print(f"session loaded for user_id={cl.user_id}")

    # --- private API (i.instagram.com) - the surfaces the bot actually uses
    step("private.account_info", cl.account_info)
    step("private.timeline_feed", cl.get_timeline_feed)
    uid = None
    me = step("private.user_info_v1", lambda: cl.user_info_by_username_v1(username))
    uid = getattr(me, "pk", None) or cl.user_id
    if uid:
        step("private.user_medias", lambda: cl.user_medias(uid, 3))
        step("private.direct_threads", lambda: cl.direct_threads(amount=5))
        medias = None
        try:
            medias = cl.user_medias(uid, 1)
        except Exception:
            pass
        if medias:
            mid = medias[0].pk
            step("private.media_comments", lambda: cl.media_comments(mid, amount=5))

    # --- public / web endpoints (www.instagram.com)
    step("public.web_profile_info", lambda: cl.user_info_by_username(username))
    step("public.gql_user_info", lambda: cl.user_info_by_username_gql(username))

    # --- after a pause, is a throttle clearing?
    print("sleeping 45s, then retrying the public endpoint ...")
    time.sleep(45)
    step("public.web_profile_info#retry", lambda: cl.user_info_by_username(username))
    return 0


if __name__ == "__main__":
    sys.exit(main())
