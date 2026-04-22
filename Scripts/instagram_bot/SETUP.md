# @gobi_automates — Instagram Content Bot

Daily pipeline that scrapes competitor Instagram accounts, finds the top 3 videos
that crossed 10,000+ views, explains why they worked using Claude AI, and generates
5 spin ideas for each — saved to a dated Excel CRM. Runs every day at **10:00 PM PT**.
Zero repeats. Catches late-blooming viral videos automatically.

## Pipeline

```
competitors.json
      │
      ▼
[Stage 1] Instaloader — FREE, no API key
  → pulls only posts from the last 24 hours per competitor
      │
      ▼
[Stage 2] Qualify & Rank (SQLite dedup)
  Pass A: new posts ingested into DB
  Pass B: posts from last 7 days re-checked for view growth (late bloomers)
  → filter: videos only, ≥10,000 views, NOT already analyzed
  → rank top 3 by current view count
      │
      ▼
[Stage 3] Claude AI Analysis (claude-sonnet-4-6)
  → "Why It Worked" — hook, trend, format, algorithm, emotion
  → Key patterns to steal for @gobi_automates
  → 5 spin variations (different angles, formats, hooks)
      │
      ▼
[Stage 4] Excel CRM + mark analyzed in DB (never repeats)
  → output/instagram_crm_YYYYMMDD.xlsx
```

## Why no repeats?

Every post analyzed is permanently marked in `output/posts.db` (SQLite).
The bot only surfaces posts that are:
1. Newly scraped (last 24h), OR
2. Were seen before but just crossed 10K views (late bloomers)
AND have never been analyzed before.

## API Keys needed

| What | Why | Cost |
|------|-----|------|
| Anthropic API key | Claude analyzes posts at 10pm PT — runs as a background process, not inside your Claude Code session | ~$0.04/day (~$1.20/mo) |
| Instagram login | Burner account to scrape profiles without hitting rate limits | Free — just make a throwaway IG account |

**Note:** Instaloader (the scraper) is completely free. No Apify needed.

## Quick Start

### 1. Get your Anthropic API key
→ `console.anthropic.com/settings/api-keys`

### 2. Make a burner Instagram account
Use a throwaway account (not @gobi_automates). This is what Instaloader logs
into to scrape competitor profiles reliably.

### 3. Add competitor handles to `competitors.json`
```json
{
  "handles": [
    "competitor_handle_1",
    "competitor_handle_2",
    "competitor_handle_3"
  ]
}
```
No `@` symbol. Add as many as you want.

### 4. Run setup
```bash
cd Scripts/instagram_bot
bash setup.sh
```

Prompts for your Anthropic key + burner IG credentials, installs deps,
and registers the bot as a systemd service (Linux) or LaunchAgent (macOS).

### 5. Test it manually
```bash
cd Scripts/instagram_bot
source .venv/bin/activate
python main.py
```

### 6. Check your CRM
```
output/
  instagram_crm_20250420.xlsx  ← today's report
  posts.db                     ← SQLite: all posts ever seen, view growth history
  run.log                      ← pipeline execution log
```

## File map

| File | What it does |
|------|-------------|
| `main.py` | Orchestrates all 4 stages |
| `scraper.py` | Instaloader: pulls last 24h of posts per competitor |
| `database.py` | SQLite: stores all posts, view snapshots, analyzed flag |
| `qualifier.py` | Dedup, late-bloomer re-check, rank top N |
| `analyzer.py` | Claude AI: why it worked + 5 spins |
| `crm.py` | Styled Excel CRM with summary + detail tabs |
| `scheduler.py` | APScheduler daemon at 22:00 America/Los_Angeles |
| `config.py` | Env vars and constants |
| `competitors.json` | Your competitor handle list |
| `setup.sh` | One-command setup |

## Scheduler commands (Linux)
```bash
systemctl --user status instagram-content-bot
journalctl --user -u instagram-content-bot -f   # live logs
systemctl --user restart instagram-content-bot
```

## Scheduler commands (macOS)
```bash
launchctl unload ~/Library/LaunchAgents/com.gobi_automates.instagram-bot.plist
launchctl load ~/Library/LaunchAgents/com.gobi_automates.instagram-bot.plist
tail -f Scripts/instagram_bot/output/launchd.log
```
