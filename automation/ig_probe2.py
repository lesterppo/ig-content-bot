#!/usr/bin/env python3
"""Second-round IG probe: the exact surfaces the bot uses, with retries.

Read-only (no posting). Prints one line per check.
"""
import json
import os
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


def step(label, fn, attempts=1, delays=(10, 30)):
    for i in range(attempts):
        t0 = time.time()
        try:
            r = fn()
            print(f"[{label}] OK ({time.time() - t0:.1f}s) -> {str(r)[:120]}")
            return r
        except Exception as e:  # noqa: BLE001
            msg = f"{type(e).__name__}: {str(e)[:150]}"
            if i + 1 < attempts:
                log_wait = delays[i] if i < len(delays) else 30
                print(f"[{label}] try{i + 1} FAIL ({time.time() - t0:.1f}s) {msg} "
                      f"-> retry in {log_wait}s")
                time.sleep(log_wait)
            else:
                print(f"[{label}] FAIL ({time.time() - t0:.1f}s) {msg}")
    return None


def main():
    username = os.environ.get("IG_USERNAME", "")
    sj = os.environ.get("IG_SESSION_JSON", "")
    cl = Client(settings={"uuids": dict(UUIDS)})
    cl.delay_range = [1, 2]
    cl.set_settings(json.loads(sj))
    cl.username = username
    uid = cl.user_id
    print(f"session loaded user_id={uid}")

    medias = step("user_medias", lambda: cl.user_medias(uid, 3), attempts=2)
    if medias:
        newest = medias[0]
        print(f"  newest post code={newest.code} taken_at={newest.taken_at}")
        step("media_comments", lambda: cl.media_comments(newest.pk, amount=10),
             attempts=2)
        step("media_info", lambda: cl.media_info(newest.pk), attempts=2)

    step("account_info(after warmup)", cl.account_info, attempts=2)
    step("direct_threads(amount=5)", lambda: cl.direct_threads(amount=5),
         attempts=2)
    step("direct_threads(full=False)",
         lambda: cl.direct_threads(amount=5, full=False), attempts=1)
    step("direct_inbox_v2_raw", lambda: cl.private_request("direct_v2/inbox/", params={
        "visual_message_return_type": "unseen",
        "thread_message_limit": "10",
        "persistentBadging": "true",
        "limit": "20",
    }), attempts=1)
    step("user_info_by_username_v1", lambda: cl.user_info_by_username_v1(username),
         attempts=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
