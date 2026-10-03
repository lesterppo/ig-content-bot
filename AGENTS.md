# AGENTS.md — runbook for deploying and operating ig-content-bot

Audience: an AI agent (or a careful human) setting this repo up on a fresh
Linux machine. Follow it in order; every step has an expected result.

---

## 0. What it does

Daily, the workflow generates an image with web Gemini, posts it to the
Instagram Story + Feed of **@ppoppo205**, then screens new comments and DMs with
a free NVIDIA model and replies / skips / escalates. Bookmarks live in
`automation/state.json` and are committed back after each run.

## 1. Hard constraints — check these BEFORE anything else

**C1 — The Instagram session must be trusted; rebuild it from a browser login.**
Measured 2026-10-03: a session created with
`automation/session_from_browser.py --test-write` (browser `sessionid` →
`login_by_sessionid`) performed reads **and writes** and the live run published
feed + story from a GitHub-hosted runner (`writes 5/5 ok`). An older stored
session JSON failed every write from the same runners
(`login_required` / `Please wait a few minutes` / HTTP 400). So: when writes
fail, rebuild the session first. Only if a fresh session still fails writes on a
cloud host should you move to a residential self-hosted runner (step 6b).

**C2 — Web Gemini cookies (GEMINI_SID/GEMINI_TS) rotate on use.**
A cookie pushed to GitHub secrets goes stale within a run or two (observed: run
N OK, run N+1 `UNAUTHENTICATED`, refresh fixed it). A self-hosted runner with a
signed-in browser refreshes them automatically at the start of every run. On
GitHub-hosted runners you must push fresh cookies right before each run.

If a constraint is violated the run still completes: the image is generated and
every blocked Instagram action is logged, not crashed.

## 2. Machine prerequisites

* Linux with `python3` (≥3.10), `git`, `curl`, `gh` (logged in: `gh auth status`)
* **A residential internet connection** (C1). Check with the probe in step 6.
* A desktop browser (Firefox recommended) that can be signed in to
  `instagram.com` and `gemini.google.com`. On a headless VM install
  `firefox` (or `chromium`) — the cookie readers need its profile on disk.
* The machine must be powered on at the scheduled cron time
  (`30 1 * * *` UTC = 09:30 HKT by default; change it in
  `.github/workflows/content-bot.yml` if the machine is usually off then).

## 3. Clone and install

```sh
git clone https://github.com/<owner>/ig-content-bot && cd ig-content-bot
python3 -m venv .venv
.venv/bin/pip install -r automation/requirements.txt
.venv/bin/pip install gemini-webapi loguru
```

Expected: no errors. `browser_cookie3` is required on this machine — the next
two steps use it.

## 4. Instagram session (do this in the machine's browser)

1. Open `https://www.instagram.com/` in the machine's browser and log in as
   **ppoppo205**. Solve any challenge interactively; leave the tab logged in.
2. Build and verify the session:

   ```sh
   .venv/bin/python automation/session_from_browser.py --test-write
   ```

   Expected output:

   ```
   firefox: N instagram cookies, sessionid=yes
   login_by_sessionid OK (…s) user_id=… username=ppoppo205
   verified: @ppoppo205 (pk 15904713306)
   write test OK (liked + unliked the newest post)
   session written to automation/.session.json (mode 600, git-ignored)
   ```

   `write test OK` is the proof that this machine's IP can post (C1). If it
   says `write test FAILED`, this machine's egress is datacenter-class — move to
   a residential host before continuing.
3. Store it as a secret (never commit it):

   ```sh
   gh secret set IG_SESSION_JSON -R <owner>/ig-content-bot < automation/.session.json
   ```

## 5. Gemini session (same machine, same browser)

Log in at `https://gemini.google.com/` in the browser, then:

```sh
.venv/bin/python automation/gemini-cli.py --init --browser firefox
.venv/bin/python automation/gemini-cli.py --account-status
```

Expected: `{"ok": true, "action": "init", "auth_src": "browser:firefox", …}` then
an `--account-status` JSON whose `status_name` is `AVAILABLE` and whose `emails`
lists the intended account.

Quick image sanity check (writes a PNG, ~20 s):

```sh
mkdir -p /tmp/probe && .venv/bin/python automation/gemini-cli.py --img \
  "editorial test portrait, one subject" --save-images /tmp/probe -o /tmp/probe/out
ls -la /tmp/probe   # gemini_img_0.png
```

## 6. Secrets, variables, runner

```sh
gh secret set NVIDIA_API_KEY -R <owner>/ig-content-bot      # free NVIDIA NIM key
gh secret set IG_USERNAME    -R <owner>/ig-content-bot      # ppoppo205
```

6a. **GitHub-hosted runner (works, simplest).** Leave `CI_RUNNER` unset. Fresh
    images require fresh Gemini cookies before each run (C2), so pair the
    schedule with something that pushes them (e.g. a cron on the machine that
    stays signed in to gemini.google.com).

6b. **Self-hosted runner (recommended: removes the cookie problem entirely).**
    Run on a machine with a signed-in browser that is powered on at the cron
    time:

    ```sh
    gh variable set CI_RUNNER --body "self-hosted" -R <owner>/ig-content-bot
    bash scripts/install_runner.sh <owner>/ig-content-bot
    gh api repos/<owner>/ig-content-bot/actions/runners \
      --jq '.runners[] | "\(.name) \(.status) \(.labels | map(.name) | join(","))"'
    ```

    Expected: one entry, `online`, labels including `self-hosted`.

## 7. Verify with the CI probe (mandatory)

Actions → **CI probe** → *Run workflow*, or:

```sh
gh workflow run ci-probe.yml -R <owner>/ig-content-bot
gh run watch $(gh run list -R <owner>/ig-content-bot -L1 --json databaseId --jq '.[0].databaseId')
```

Require ALL of:

* **gemini job** — `"status_name": "AVAILABLE"`; an image line
  (`{"ok": true, "imgs": 1, …}`); NVIDIA models printing `OK`.
  (`UNAUTHENTICATED` here means the cookies are stale → C2.)
* **instagram job** — the last two lines:

  ```
  SUMMARY reads N/M ok, writes K/K ok
  VERDICT: residential-class egress — the bot can post and engage here.
  ```

  With a trusted session this passes even on `ubuntu-latest` (verified
  2026-10-03). If writes are 0/5 with `login_required` / `Please wait` → the
  session is not trusted: redo step 4. If it still fails, the egress IP is
  blocked → step 6b.

## 8. First live run

```sh
gh workflow run content-bot.yml -R <owner>/ig-content-bot \
  -f dry_run=false -f post_to_feed=true -f post_to_story=true -f engage=true
```

Expected log signature (this exact sequence was verified end-to-end):

```
session valid via user_medias
image saved to automation/.today.jpg
caption: '… #AIgenerated'
story published
feed post published
scanning comments on N recent post(s)
done
```

…plus a `content-bot: update bookmarks [skip ci]` commit from the *Persist
bookmark state* step. Confirm on Instagram that the post + story exist (or check
locally: `python automation/ig_probe.py` lists the newest posts).

## 9. Day-2 operations

| Situation | Action |
|---|---|
| `Auth expired` from gemini-cli | Browser session died: sign in at gemini.google.com again, rerun `--init --browser firefox`. On GitHub-hosted runners refresh the secrets instead. |
| `session valid via user_medias` missing, everything fails | IG session dead → step 4 again (and re-set the secret). |
| `Please wait a few minutes` / `login_required` on writes | The session lost trust → rebuild it from a browser login (step 4). If a *fresh* session still fails, the egress IP is the problem (VPN? datacenter host?) → step 6b. |
| NVIDIA model errors / `410 EOL` | `.venv/bin/python scripts/probe_nvidia.py`, then update `NVIDIA_MODEL`/`NVIDIA_FALLBACK_MODEL` in the workflow. |
| Runner offline | `cd ~/actions-runner && ./svc.sh status` (or `./run.sh` if installed without sudo); check the machine was on at cron time. |
| Nothing new handled | Expected when there are no new comments/DMs; `state.json` bookmarks are the source of truth. |

Scheduled runs are LIVE (only manual dispatch defaults to dry-run). To pause
automation without deleting anything, comment out the `schedule:` block.

## 10. Rules for agents working on this repo

0. **Repo visibility vs self-hosted runner:** GitHub recommends self-hosted
   runners only on *private* repositories. If this repo is public, keep it
   private (or accept that any collaborator-approved workflow change would run
   on the runner machine). Never add `pull_request` / `pull_request_target` or
   `push`-from-fork triggers to a self-hosted workflow.
1. Never post public comments from a probe. Write probes like/save the owner's
   own newest post and undo immediately.
2. Never remove the `#AIgenerated` labeling or loosen the reply safety rules in
   `content_bot.py` (no commitments, no personal details, `ESCALATE:` path).
3. Never print secret values (IG session, NVIDIA key, Gemini cookies) into logs,
   commits or chat. Use `gh secret set … < file` and keep files at mode 600.
4. Instagram actions must stay gentle: keep `delay_range`, the retry ladders and
   the bookmark logic — repeated blind retries are what get accounts flagged.
5. When changing the workflow, preserve the `vars.CI_RUNNER || 'ubuntu-latest'`
   fallback so the repo keeps working on stock runners.
