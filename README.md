# ig-content-bot

Daily Instagram content + engagement bot for **@ppoppo205**, driven by GitHub
Actions.

Each run:

1. **Generates** a tasteful glamour portrait with **web Gemini** (browser-cookie
   auth, free tier — no API key).
2. **Posts** it to the Instagram Story and Feed, labeling AI content `#AIgenerated`.
3. **Screens** new comments on recent posts with a **free NVIDIA model** — genuine
   comments get a warm reply, spam/harassment is skipped, sensitive ones are
   escalated to the owner.
4. **Screens** new DMs the same way and replies in the owner's voice.
5. Persists bookmarks to `automation/state.json`, so each run only handles what
   is new.

---

## ⚠️ Deployment constraints (the part that decides whether this works)

**1. The Instagram session must be "trusted" — rebuild it from a browser login.**

Measured on 2026-10-03 with this account:

| Session source | Reads (`user_medias`) | Writes (post / story / like / DM) |
|---|---|---|
| fresh login via `automation/session_from_browser.py` (browser `sessionid`) | ✅ | ✅ **including from GitHub-hosted runners** — the live run published feed + story and logged `writes 5/5 ok` |
| older stored session JSON | ✅ | ❌ `login_required`, `Please wait a few minutes`, HTTP 400 on every write |

So the rule is: **when writes fail, rebuild the session from a browser login
first** (step 4 of AGENTS.md). Only if a genuinely fresh session still fails
should you suspect the egress IP (VPN on, cloud/datacenter host) — in that case
deploy a self-hosted runner on a residential connection
(`scripts/install_runner.sh`) and set the repo variable `CI_RUNNER=self-hosted`.

**2. Web Gemini cookies: a self-refreshing chain keeps them alive in CI.**

Google rotates `__Secure-1PSIDTS` server-side, so a cookie stored as a GitHub
secret goes stale. `accounts.google.com/RotateCookies` issues a fresh one when
called with the **full `.google.com` jar** (SID plus the account cookies — SID+TS
alone gets 429). The workflows use that:

* `actions/cache` stores the jar between runs (`gemini-jar-*`, newest wins);
* `automation/refresh_cookies.py` gathers candidates (browser → cache → secrets),
  probes each with the CLI, rotates when none authenticates, exports
  `GEMINI_SID`/`GEMINI_TS` for the run, and writes the winning jar back;
* secrets: **`GEMINI_COOKIES_JSON`** (full jar — build it with
  `automation/harvest_cookies.py --browser firefox`) plus `GEMINI_SID`/`GEMINI_TS`
  as a cold fallback.

So a scheduled run on `ubuntu-latest` keeps itself supplied. Only if the cache
is evicted *and* the secrets have gone stale (e.g. nobody ran the bot for a week)
does a human need to re-harvest: `harvest_cookies.py` → `gh secret set
GEMINI_COOKIES_JSON`. Self-hosted runners additionally refresh straight from
their own browser, which makes the chain unnecessary.

**3. NVIDIA free models get retired without notice** (several went 410 EOL on
2026-10-03). Run `scripts/probe_nvidia.py` when a run fails and update
`NVIDIA_MODEL` / `NVIDIA_FALLBACK_MODEL` in the workflow.

---

## Schedule

* Cron `30 1 * * *` (01:30 UTC = 09:30 HKT, daily) — set it to an hour when the
  runner machine is normally powered on.
* Manual: Actions → **Content bot** → *Run workflow* (dry-run by default).

## Repository variables / secrets

| Name | Kind | Purpose |
|---|---|---|
| `CI_RUNNER` | variable | Runner label; set to `self-hosted` for the residential machine. Unset = `ubuntu-latest`. |
| `IG_USERNAME` | secret | Instagram username |
| `IG_PASSWORD` | secret | Password — fallback only; password logins get challenged |
| `IG_SESSION_JSON` | secret | instagrapi session JSON (preferred). Build with `automation/session_from_browser.py` |
| `NVIDIA_API_KEY` | secret | NVIDIA NIM key (free tier) for captions/replies |
| `GEMINI_COOKIES_JSON` | secret | **Full** `.google.com` cookie jar (anchor for the rotating chain) — `automation/harvest_cookies.py` |
| `GEMINI_SID` | secret | Google `__Secure-1PSID` (cold fallback) |
| `GEMINI_TS` | secret | Google `__Secure-1PSIDTS` (cold fallback) |

## Verify a deployment

Actions → **CI probe** → *Run workflow*:

* **gemini** job — cookie/auth status, live image generation, NVIDIA model list.
* **instagram** job — read/write surface matrix and a verdict line:
  `residential-class egress` vs `writes are blocked → datacenter-class egress`.

## Safety

* `DRY_RUN` defaults to `true` on manual dispatch; scheduled runs go live.
* Replies: max 280 chars, no commitments, no personal details, never reveals AI.
* The model may answer `ESCALATE:` — then nothing is sent and the log flags it.
* Write probes in `automation/ig_probe.py` only like/save your own newest post
  and undo immediately; no public comments.
* All generated imagery is tasteful, fully clothed, adult fashion-editorial style.

## Local run

```sh
python3 -m venv .venv && .venv/bin/pip install -r automation/requirements.txt
.venv/bin/pip install gemini-webapi loguru
python automation/session_from_browser.py --test-write      # build/verify session
IG_SESSION_JSON="$(cat automation/.session.json)" IG_USERNAME=ppoppo205 \
NVIDIA_API_KEY=... DRY_RUN=true python automation/content_bot.py
```

See **AGENTS.md** for the full deployment runbook (written for an AI agent).
