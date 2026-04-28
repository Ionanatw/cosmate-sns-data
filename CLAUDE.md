# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Does

SNS data pipeline for CosMate — scrapes Threads (and Instagram), analyzes engagement, renders HTML dashboards, syncs metrics to Notion, and deploys to Cloudflare Pages. Two main pipelines:

- **Weekly** (`scripts/weekly.sh`): Threads 市場熱榜 for anime/love/cosplay + CosMate 自家帳號表現 → `index.html` 4-tab dashboard
- **Daily** (`scripts/daily.sh`): Threads 72h hot posts across the same 3 topics → `daily/index.html`
- **Metrics sync** (`scripts/fetch_insights.sh`): Threads Graph API → Notion Posts DB (5 accounts)
- **IG sync** (`scripts/fetch_ig_insights.sh`): Instagram Basic Display API → Notion Posts DB

## Common Commands

```bash
# Weekly pipeline (scrape + analyze + render; no deploy)
bash scripts/weekly.sh

# Weekly pipeline + deploy to Cloudflare Pages
bash scripts/weekly.sh deploy

# Weekly: skip re-scrape, only re-analyze + re-render from existing raw data
bash scripts/weekly.sh skip-scrape

# Daily pipeline
bash scripts/daily.sh               # full (with AI commentary)
bash scripts/daily.sh no-ai         # skip Claude AI analysis
bash scripts/daily.sh skip-scrape   # re-render from existing raw data

# Threads metrics: fetch insights for one or all accounts
bash scripts/fetch_insights.sh 14 cosmate
bash scripts/fetch_insights.sh 7 all

# Threads metrics → sync to Notion
bash scripts/fetch_insights.sh 3 all --sync-notion

# IG metrics → sync to Notion
bash scripts/fetch_ig_insights.sh 3 cosmate --sync-notion

# Individual pipeline steps
python3 scripts/scrape_playwright_topics.py            # Playwright scraper (preferred)
python3 scripts/scrape_multi_topic.py anime love cosplay  # Apify fallback
python3 scripts/scrape_cosmate.py --days 30            # CosMate official Graph API
python3 scripts/analyze_by_topic.py --all --days 30    # analyze all topics
python3 scripts/render_index.py                        # render weekly HTML
python3 scripts/render_daily.py --with-ai              # render daily HTML + AI commentary
python3 scripts/render_archive_index.py                # update archive list
python3 scripts/ai_analyze.py                          # run Claude analysis on top posts
bash scripts/deploy.sh                                 # deploy to Cloudflare Pages
```

## Environment & Credentials

**Local `.env`** (gitignored, in project root):
```
APIFY_TOKEN=...
ANTHROPIC_API_KEY=...
```

**Local `.env.threads`** at `/Users/ionachen/Documents/Claude/project/.env.threads`:
- `THREADS_TOKEN_<ACCOUNT>` / `THREADS_USERID_<ACCOUNT>` / `THREADS_USERNAME_<ACCOUNT>` for accounts: `cosmate`, `olie`, `dadana`, `kiki`, `amy`

**Local `.env.instagram`** at `/Users/ionachen/Documents/Claude/project/.env.instagram`:
- `IG_TOKEN_COSMATE` / `IG_USERID_COSMATE` / `IG_USERNAME_COSMATE`

**GitHub Secrets** (used by GHA): same vars as above, plus `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `NOTION_TOKEN`, `NOTION_THREADS_DB_ID`, `NOTION_POSTS_DB_ID`.

**Playwright cookies** (Threads scraper):
```bash
# One-time: export cookies from local Chrome (must be logged in to Threads)
python3 /Users/ionachen/Documents/Claude/cosmate-ai-nexus/skills/threads-analytics/scripts/scrape_threads.py --dump-cookies ~/.cosmate/threads_cookies.json
```
Playwright is preferred over Apify because it captures `repost`/`share` counts. Falls back to Apify automatically if cookies are missing.

## Architecture

```
scripts/
├── scrape_playwright_topics.py  ← Primary Threads scraper (Playwright + cookies)
│   └── calls cosmate-ai-nexus/skills/threads-analytics/scripts/scrape_threads.py
├── scrape_multi_topic.py        ← Apify fallback scraper
├── scrape_cosmate.py            ← CosMate account via official Threads Graph API
├── analyze_by_topic.py          ← Per-topic analysis (30d + 7d + zh-TW filter)
├── analyze.py                   ← Legacy single-topic analyzer (deprecated, kept for reference)
├── ai_analyze.py                ← Claude API: generate AI insights per topic
├── render_index.py              ← Render weekly 4-tab index.html
├── render_daily.py              ← Render daily/index.html
├── render_archive_index.py      ← Render reports/archive/index.html listing
├── sync_to_notion.py            ← Threads metrics → Notion Posts DB
├── sync_ig_to_notion.py         ← IG metrics → Notion Posts DB
├── fetch_insights.sh            ← Orchestrates Threads API + optional Notion sync
├── fetch_ig_insights.sh         ← Orchestrates IG API + optional Notion sync
├── weekly.sh                    ← Weekly pipeline orchestrator
├── daily.sh                     ← Daily pipeline orchestrator
└── deploy.sh                    ← Cloudflare Pages deploy via wrangler

data/
├── raw/                         ← Raw JSON from scrapers (gitignored; {topic}_{timestamp}.json)
├── per_topic/                   ← Structured analysis JSON read by render scripts (gitignored)
└── daily/                       ← Daily analysis output (gitignored)

daily/index.html                 ← Daily dashboard (committed by GHA)
index.html                       ← Weekly dashboard (gitignored locally, committed by GHA)
reports/archive/                 ← Weekly report archive
```

## Data Flow

1. **Scrape** → `data/raw/{topic}_{timestamp}.json`
2. **Analyze** (`analyze_by_topic.py`) → `data/per_topic/{topic}.json` with Type A–X classification
3. **AI Analyze** (`ai_analyze.py`) → injects `ai_insight` field into `data/per_topic/{topic}.json`
4. **Render** → `index.html` / `daily/index.html` (self-contained HTML with embedded JSON)
5. **Deploy** → Cloudflare Pages at `https://threads-analytics-report.pages.dev`
6. **Notion sync** → `sync_to_notion.py` upserts to Notion Posts DB

## Post Engagement Classification (Type A–X)

Defined in `scripts/analyze.py:classify_posts()`. Uses percentile thresholds on the batch:

| Type | Rule |
|------|------|
| A 全能爆款 🔥 | likes ≥ P90 AND comments ≥ P90 |
| B 私域擴散型 ✈️ | reposts+shares ≥ P75 (not A) |
| C 戰場議論型 💬 | comments ≥ P75 AND comment_rate > 3% (not A) |
| D 靜默共鳴型 ❤️ | likes ≥ P75 AND comments < P25 (not A) |
| E 穩定互動型 📊 | total_engagement ≥ P50 AND likes ≥ P25 (not A–D) |
| X 長尾內容 🫧 | everything else |

Only A–E appear in ranked lists; X is excluded.

## GitHub Actions

- **`daily.yml`**: Runs at 01:30 UTC (09:30 GMT+8) — full daily pipeline + deploy + commit
- **`weekly.yml`**: Weekly pipeline
- **`metrics-sync.yml`**: Daily at 01:30 UTC — Threads + IG metrics → Notion for all accounts

CI uses `wrangler-action@v3` for deploy (no local wrangler needed in CI). Python deps required in CI: `apify-client requests python-dateutil pytz certifi`. Sync scripts use only stdlib.

## Known Paths / External Dependencies

- Playwright scraper delegates to: `/Users/ionachen/Documents/Claude/cosmate-ai-nexus/skills/threads-analytics/scripts/scrape_threads.py`
- Cloudflare Pages project name: `threads-analytics-report`
- Notion Posts DB ID (local reference): `2106fedce91a81389a54c223533d481b`
- Threads accounts tracked: `cosmate`, `olie`, `dadana`, `kiki`, `amy`
- IG accounts tracked: `cosmate` only (expandable in `fetch_ig_insights.sh:ALL_ACCOUNTS`)
