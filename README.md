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

**1. Instagram only allows writes from residential/mobile IPs.**

Measured on 2026-10-03 with the same account and the same session JSON:

| Surface | GitHub-hosted runner (Azure IP) | Residential IP |
|---|---|---|
| `user_medias` (read own posts) | ✅ works | ✅ works |
| `media_comments` (read) | ❌ `Please wait a few minutes` | ✅ works |
| `photo_upload` / story | ❌ `login_required` | ✅ works |
| `direct_threads` / DM send | ❌ HTTP 400 | ✅ works |
| like / save | ❌ `We're sorry, but something went wrong` | ✅ works |

Retries do not help — Instagram blocks the whole datacenter IP class for this
account. **The bot must run on a self-hosted runner on a residential
connection** (`scripts/install_runner.sh`), and the repo variable
`CI_RUNNER=self-hosted` selects it. On `ubuntu-latest` the workflow still runs,
generates the image, and logs every Instagram write as failed.

**2. Web Gemini cookies rotate on use.**

Google rotates `__Secure-1PSIDTS` server-side whenever the cookies are used, so
a cookie stored as a GitHub secret goes stale within a run or two. Two ways to
cope:

* **Self-hosted runner (recommended):** the workflow runs
  `gemini-cli.py --init --browser firefox` at the start of every run and reads
  fresh cookies from the machine's own signed-in Firefox. Nothing to maintain.
* **GitHub-hosted runner:** push fresh `GEMINI_SID`/`GEMINI_TS` secrets shortly
  before each run (a cookie harvested hours earlier usually fails with
  `Auth expired`).

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
| `GEMINI_SID` | secret | Google `__Secure-1PSID` cookie (web Gemini) |
| `GEMINI_TS` | secret | Google `__Secure-1PSIDTS` cookie (web Gemini) |

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
