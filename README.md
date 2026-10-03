# ig-content-bot

Daily Instagram content + engagement bot for **@ppoppo205**, running on GitHub Actions.

Each run:
1. **Generates** a tasteful glamour portrait via the Gemini API (free tier).
2. **Posts** it to the Instagram Story and Feed (AI-generated content is labeled `#AIgenerated`).
3. **Screens** new comments on recent posts with a free NVIDIA model — genuine comments get a warm reply; spam/harassment is skipped; sensitive ones are escalated for owner review.
4. **Screens** new DMs the same way and replies in the owner's voice.
5. Persists bookmarks to `automation/state.json` so each run only handles what's new.

## Schedule

- Cron: `30 1 * * *` (01:30 UTC = 09:30 HKT, daily).
- Manual: Actions → "Content bot" → Run workflow (dry-run by default).

## Secrets

| Secret | Purpose |
|---|---|
| `IG_USERNAME` | Instagram username |
| `IG_PASSWORD` | Instagram password (fallback; prefer `IG_SESSION_JSON`) |
| `IG_SESSION_JSON` | Pre-authenticated instagrapi session — avoids password logins from CI IPs, which trigger challenges |
| `NVIDIA_API_KEY` | NVIDIA API key (free tier) for reply/caption drafting |
| `GEMINI_API_KEY` | Gemini API key (AI Studio, free tier) for image generation |

## Safety

- `DRY_RUN` defaults to `"true"` on manual dispatch; scheduled runs go live.
- Replies are capped at 280 chars, never make commitments, never share personal details.
- The NVIDIA model can return `ESCALATE:` instead of a reply — nothing is sent then.
- All generated imagery is tasteful, fully clothed, adult fashion-editorial style.

## Local test

```sh
pip install -r automation/requirements.txt
IG_USERNAME=... IG_SESSION_JSON='...' NVIDIA_API_KEY=... GEMINI_API_KEY=... \
  DRY_RUN=true python automation/content_bot.py
```
