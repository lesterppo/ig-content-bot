#!/usr/bin/env python3
"""Instagram surface probe — answers "can this machine actually run the bot?".

Run this on a new machine before trusting a schedule. It is safe: the only
write probes like/save the owner's own newest post and undo both immediately.

Reading the output:
  * reads OK + writes OK         -> residential-class egress: the full bot works
  * reads OK + writes throttled  -> datacenter-class egress (GitHub-hosted
                                    runners, cloud VMs): posting/comments/DM
                                    replies will fail. See AGENTS.md.
  * nothing works                -> the session is dead: rebuild it with
                                    automation/session_from_browser.py

Usage:
  IG_USERNAME=... IG_SESSION_JSON='...' python automation/ig_probe.py
  (without IG_SESSION_JSON the session is read from SESSION_PATH,
   default automation/.session.json)
"""
import json
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

RESULTS = {"read": [], "write": []}


def step(group, label, fn, attempts=1, delays=(10,)):
    for i in range(attempts):
        t0 = time.time()
        try:
            r = fn()
            print(f"[{group}.{label}] OK ({time.time() - t0:.1f}s) -> {str(r)[:110]}")
            RESULTS[group].append((label, True))
            return r
        except Exception as e:  # noqa: BLE001 - diagnostic
            msg = f"{type(e).__name__}: {str(e)[:150]}"
            if i + 1 < attempts:
                wait = delays[i] if i < len(delays) else delays[-1]
                print(f"[{group}.{label}] try{i + 1} FAIL -> retry in {wait}s ({msg[:90]})")
                time.sleep(wait)
            else:
                print(f"[{group}.{label}] FAIL ({time.time() - t0:.1f}s) {msg}")
                RESULTS[group].append((label, False))
    return None


def load_client():
    username = os.environ.get("IG_USERNAME", "")
    session_json = os.environ.get("IG_SESSION_JSON", "")
    session_path = os.environ.get("SESSION_PATH", "automation/.session.json")
    if not session_json and os.path.exists(session_path):
        session_json = open(session_path).read()
    if not session_json:
        print(f"no IG_SESSION_JSON and no {session_path} — cannot probe")
        sys.exit(2)
    cl = Client(settings={"uuids": dict(UUIDS)})
    cl.delay_range = [1, 2]
    cl.set_settings(json.loads(session_json))
    cl.username = username
    return cl


def main():
    cl = load_client()
    uid = cl.user_id
    print(f"session loaded: user_id={uid} username={cl.username}")

    medias = step("read", "user_medias", lambda: cl.user_medias(uid, 3), attempts=2)
    if medias:
        newest = medias[0]
        print(f"  newest post: {newest.code} taken_at={newest.taken_at}")
        step("read", "media_comments", lambda: cl.media_comments(newest.pk, amount=5),
             attempts=2)
    step("read", "account_info", cl.account_info, attempts=1)
    step("read", "user_info_v1", lambda: cl.user_info_by_username_v1(cl.username), attempts=1)
    step("read", "direct_threads", lambda: cl.direct_threads(amount=5), attempts=2)
    step("read", "web_profile_info(public)",
         lambda: cl.user_info_by_username(cl.username), attempts=1)

    if medias:
        pk = medias[0].pk
        step("write", "media_like", lambda: cl.media_like(pk), attempts=1)
        step("write", "media_unlike", lambda: cl.media_unlike(pk), attempts=1)
        step("write", "media_save", lambda: cl.media_save(pk), attempts=1)
        step("write", "media_unsave", lambda: cl.media_unsave(pk), attempts=1)
        step("write", "direct_send(self)", lambda: cl.direct_send(
            "probe: ignore", user_ids=[int(uid)]), attempts=1)

    r_ok = sum(1 for _l, ok in RESULTS["read"] if ok)
    w_ok = sum(1 for _l, ok in RESULTS["write"] if ok)
    print()
    print(f"SUMMARY reads {r_ok}/{len(RESULTS['read'])} ok, "
          f"writes {w_ok}/{len(RESULTS['write'])} ok")
    if RESULTS["write"] and w_ok == len(RESULTS["write"]):
        print("VERDICT: residential-class egress — the bot can post and engage here.")
    elif r_ok:
        print("VERDICT: reads work but writes are blocked → datacenter-class egress.")
        print("         Run the bot on a residential-connection self-hosted runner "
              "(see AGENTS.md).")
    else:
        print("VERDICT: session unusable → rebuild it with "
              "automation/session_from_browser.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
