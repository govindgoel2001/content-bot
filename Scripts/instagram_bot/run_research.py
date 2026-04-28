#!/usr/bin/env python3
"""
Instagram competitor research pipeline — outlier-scored, MWF.
Scrape → state update → baseline → winner detection → analysis → outputs.

Outputs written to output/:
  posts_state.json        persistent state
  YYYY-MM-DD.json         today's run data
  YYYY-MM-DD.md           human-readable summary
  winners.csv             all-time winners (appended)

Flags:
  --since YYYY-MM-DD   restrict winner window to this date → today; also
                        lowers MIN_REELS_FOR_BASELINE to 3 so short windows
                        still produce baselines (e.g. run_research.py --since 2026-04-23)
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import anthropic
import requests

from notion_winners import push_winners

# ── Config ────────────────────────────────────────────────────────────────────
APIFY_API_KEY     = os.environ["APIFY_API_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
NOTION_API_KEY    = os.environ.get("NOTION_API_KEY", "")
NOTION_WINNERS_DB = os.environ.get("NOTION_WINNERS_DB_ID", "")

ACTOR_ID   = "apify~instagram-scraper"
APIFY_BASE = "https://api.apify.com/v2"

OUTPUT_DIR       = Path(__file__).parent / "output"
COMPETITORS_PATH = Path(__file__).parent / "competitors.json"
STATE_PATH       = OUTPUT_DIR / "posts_state.json"
WINNERS_CSV      = OUTPUT_DIR / "winners.csv"

_now             = datetime.now(timezone.utc)
TODAY            = _now.date().isoformat()
NOW_ISO          = _now.isoformat()

OUTLIER_THRESHOLD      = 2.5
VIRAL_THRESHOLD        = 8.0
MIN_REELS_FOR_BASELINE = 10   # lowered to 3 automatically when --since is used
SCRAPE_DAYS            = 30
WINNER_WINDOW_DAYS     = 14

CSV_HEADERS = [
    "run_date", "handle", "url", "views", "outlier_score", "viral_flag",
    "why_it_worked", "spin_angle_1", "spin_angle_2", "spin_angle_3",
    "spin_angle_4", "spin_angle_5",
]


def log(msg: str) -> None:
    print(f"[{NOW_ISO[:19]}] {msg}", flush=True)


# ── Step 1: Load handles ──────────────────────────────────────────────────────
def load_handles() -> list[str]:
    with open(COMPETITORS_PATH) as f:
        return json.load(f)["handles"]


# ── Step 2: Scrape via Apify (async run + poll) ───────────────────────────────
def scrape_apify(handles: list[str]) -> list[dict]:
    urls = [f"https://www.instagram.com/{h}/reels/" for h in handles]
    log(f"Starting Apify run for {len(handles)} handles…")

    r = requests.post(
        f"{APIFY_BASE}/acts/{ACTOR_ID}/runs",
        params={"token": APIFY_API_KEY},
        json={
            "directUrls":   urls,
            "resultsType":  "posts",
            "resultsLimit": 50,
            "addParentData": False,
        },
        timeout=30,
    )
    r.raise_for_status()
    run_data   = r.json()["data"]
    run_id     = run_data["id"]
    dataset_id = run_data["defaultDatasetId"]
    log(f"Run ID: {run_id}")

    while True:
        sr = requests.get(
            f"{APIFY_BASE}/actor-runs/{run_id}",
            params={"token": APIFY_API_KEY},
            timeout=15,
        )
        sr.raise_for_status()
        status = sr.json()["data"]["status"]
        log(f"Apify status: {status}")
        if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            break
        time.sleep(10)

    if status != "SUCCEEDED":
        raise RuntimeError(f"Apify run ended with status: {status}")

    ir = requests.get(
        f"{APIFY_BASE}/datasets/{dataset_id}/items",
        params={"token": APIFY_API_KEY, "clean": "true"},
        timeout=30,
    )
    ir.raise_for_status()
    items = ir.json()
    log(f"Fetched {len(items)} raw items")
    return items


def strip_fields(item: dict, handle_map: dict) -> dict | None:
    """Keep only the 7 allowed fields; discard non-reels."""
    views = item.get("videoPlayCount") or item.get("videoViewCount") or 0
    if not views:
        return None

    owner   = (item.get("ownerUsername") or "").lower()
    handle  = handle_map.get(owner, owner)
    sc      = item.get("shortCode") or item.get("id") or ""
    url     = item.get("url") or f"https://www.instagram.com/reel/{sc}/"

    return {
        "url":       url,
        "handle":    handle,
        "posted_at": item.get("timestamp", ""),
        "views":     int(views),
        "likes":     int(item.get("likesCount") or 0),
        "comments":  int(item.get("commentsCount") or 0),
        "caption":   (item.get("caption") or "")[:2000],  # internal only, never written to CSV
    }


# ── Step 3: Update state ──────────────────────────────────────────────────────
def load_state() -> dict:
    if STATE_PATH.exists():
        with open(STATE_PATH) as f:
            return json.load(f)
    return {"posts": {}}


def save_state(state: dict) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def upsert_post(state: dict, post: dict) -> None:
    url   = post["url"]
    posts = state["posts"]

    if url not in posts:
        posts[url] = {
            "handle":           post["handle"],
            "posted_at":        post["posted_at"],
            "first_seen":       TODAY,
            "last_seen":        TODAY,
            "views_history":    [],
            "peak_views":       0,
            "winner_logged":    False,
            "winner_logged_at": None,
            "winner_score":     None,
        }

    entry = posts[url]
    entry["last_seen"] = TODAY

    seen_dates = {v["date"] for v in entry["views_history"]}
    if TODAY not in seen_dates:
        entry["views_history"].append({"date": TODAY, "views": post["views"]})

    if post["views"] > entry["peak_views"]:
        entry["peak_views"] = post["views"]


# ── Step 4: Per-handle baseline ───────────────────────────────────────────────
def compute_baselines(state: dict) -> tuple[dict, list[str]]:
    cutoff = (_now - timedelta(days=SCRAPE_DAYS)).date().isoformat()
    by_handle: dict[str, list[int]] = {}

    for entry in state["posts"].values():
        if entry["posted_at"][:10] >= cutoff:
            h = entry["handle"]
            by_handle.setdefault(h, []).append(entry["peak_views"])

    baselines: dict[str, dict] = {}
    skipped:   list[str]       = []

    for handle, views_list in by_handle.items():
        if len(views_list) < MIN_REELS_FOR_BASELINE:
            log(f"  Skipping @{handle} — only {len(views_list)} reels (need {MIN_REELS_FOR_BASELINE})")
            skipped.append(handle)
        else:
            avg = sum(views_list) / len(views_list)
            baselines[handle] = {"avg_views": round(avg, 1), "reel_count": len(views_list)}
            log(f"  @{handle}: avg {avg:,.0f} views over {len(views_list)} reels")

    return baselines, skipped


# ── Step 5: Winner detection (last 14 days only) ──────────────────────────────
def detect_winners(state: dict, baselines: dict) -> list[dict]:
    cutoff14 = (_now - timedelta(days=WINNER_WINDOW_DAYS)).date().isoformat()
    winners  = []

    for url, entry in state["posts"].items():
        if entry["posted_at"][:10] < cutoff14:
            continue
        if entry["winner_logged"]:
            continue

        handle = entry["handle"]
        if handle not in baselines or baselines[handle]["avg_views"] == 0:
            continue

        score = entry["peak_views"] / baselines[handle]["avg_views"]
        if score >= OUTLIER_THRESHOLD:
            entry["winner_logged"]    = True
            entry["winner_logged_at"] = NOW_ISO
            entry["winner_score"]     = round(score, 3)
            winners.append({
                "url":          url,
                "handle":       handle,
                "posted_at":    entry["posted_at"],
                "views":        entry["peak_views"],
                "outlier_score": round(score, 3),
                "viral_flag":   score >= VIRAL_THRESHOLD,
            })
            log(f"  WINNER: {url} — {score:.2f}x {'[VIRAL]' if score >= VIRAL_THRESHOLD else ''}")

    return winners


# ── Step 6: Analyze with Claude ───────────────────────────────────────────────
_SYSTEM = """\
You are an expert Instagram content strategist for @gobi_automates (AI automation, \
RAG, agents, no-code AI). Analyze competitor reels and generate spin angles. \
Write with varied sentence length. No em-dashes as connectors. No rule-of-three lists. \
Never use: unlock, dive into, leverage, foster, robust, seamless, cutting-edge, \
revolutionize, in today's fast-paced world, stands as testament, pivotal, landscape, \
crucial, serves as."""

_PROMPT = """\
Reel: {url}
Handle: @{handle}
Views: {views:,}
Posted: {posted_at}
Caption: {caption}

Write JSON only — no markdown, no extra text:
{{
  "why_it_worked": "2-3 sentences on hook mechanics, pattern interrupt, emotional \
trigger, and visual composition. Be specific to this reel.",
  "spin_angles": [
    "angle 1 — one sentence for @gobi_automates",
    "angle 2 — one sentence",
    "angle 3 — one sentence",
    "angle 4 — one sentence",
    "angle 5 — one sentence"
  ]
}}"""


def analyze_winner(winner: dict, state: dict) -> dict:
    caption = state["posts"].get(winner["url"], {}).get("caption", "")
    client  = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    msg = client.messages.create(
        model      = "claude-sonnet-4-6",
        max_tokens = 1024,
        system     = _SYSTEM,
        messages   = [{
            "role":    "user",
            "content": _PROMPT.format(
                url       = winner["url"],
                handle    = winner["handle"],
                views     = winner["views"],
                posted_at = winner["posted_at"],
                caption   = caption[:500],
            ),
        }],
    )

    raw = msg.content[0].text.strip()
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {"why_it_worked": raw, "spin_angles": []}

    angles = parsed.get("spin_angles", [])
    while len(angles) < 5:
        angles.append("")

    return {
        **winner,
        "why_it_worked": parsed.get("why_it_worked", ""),
        "spin_angles":   angles[:5],
    }


# ── Step 7a: JSON output ──────────────────────────────────────────────────────
def write_json(analyzed: list[dict], baselines: dict, skipped: list[str]) -> None:
    path = OUTPUT_DIR / f"{TODAY}.json"
    data = {
        "generated_at":                NOW_ISO,
        "handles_scanned":             list(baselines.keys()),
        "handles_skipped_low_volume":  skipped,
        "baselines":                   baselines,
        "winners": [
            {
                "handle":        w["handle"],
                "url":           w["url"],
                "posted_at":     w["posted_at"],
                "views":         w["views"],
                "outlier_score": w["outlier_score"],
                "viral_flag":    w["viral_flag"],
                "why_it_worked": w["why_it_worked"],
                "spin_angles":   w["spin_angles"],
            }
            for w in analyzed
        ],
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    log(f"Wrote {path.name}")


# ── Step 7b: Markdown output ──────────────────────────────────────────────────
def write_md(analyzed: list[dict], baselines: dict, skipped: list[str]) -> None:
    path  = OUTPUT_DIR / f"{TODAY}.md"
    lines = [f"# IG Research — {TODAY}\n"]
    lines.append(f"Scanned {len(baselines)} handle(s). {len(analyzed)} new winner(s).\n")

    if skipped:
        lines.append(f"Skipped low-volume: {', '.join('@' + h for h in skipped)}\n")

    if not analyzed:
        lines.append("\nNo new winners this run.\n")
    else:
        for w in analyzed:
            viral_tag = "  VIRAL" if w["viral_flag"] else ""
            lines.append(f"\n---\n")
            lines.append(f"## @{w['handle']} — {w['outlier_score']:.1f}x{viral_tag}\n")
            lines.append(f"**Reel:** {w['url']}  \n")
            lines.append(f"**Views:** {w['views']:,} &nbsp; **Posted:** {w['posted_at'][:10]}\n")
            lines.append(f"\n**Why it worked:** {w['why_it_worked']}\n")
            lines.append(f"\n**Spin angles for @gobi_automates:**\n")
            for i, angle in enumerate(w["spin_angles"], 1):
                lines.append(f"{i}. {angle}\n")

    with open(path, "w") as f:
        f.writelines(lines)
    log(f"Wrote {path.name}")


# ── Step 7c: winners.csv (append) ─────────────────────────────────────────────
def write_csv(analyzed: list[dict]) -> int:
    write_header = not WINNERS_CSV.exists()

    with open(WINNERS_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        if write_header:
            writer.writerow(CSV_HEADERS)
        for w in analyzed:
            angles = w["spin_angles"]
            writer.writerow([
                TODAY,
                w["handle"],
                w["url"],
                w["views"],
                w["outlier_score"],
                w["viral_flag"],
                w["why_it_worked"],
                angles[0] if len(angles) > 0 else "",
                angles[1] if len(angles) > 1 else "",
                angles[2] if len(angles) > 2 else "",
                angles[3] if len(angles) > 3 else "",
                angles[4] if len(angles) > 4 else "",
            ])

    with open(WINNERS_CSV) as f:
        total = sum(1 for _ in f) - 1
    log(f"winners.csv: appended {len(analyzed)}, total {total} rows")
    return total


# ── Step 8: Prune state ───────────────────────────────────────────────────────
def prune_state(state: dict) -> None:
    cutoff = (_now - timedelta(days=SCRAPE_DAYS)).date().isoformat()
    before = len(state["posts"])
    state["posts"] = {
        url: e for url, e in state["posts"].items()
        if e["last_seen"] >= cutoff
    }
    pruned = before - len(state["posts"])
    if pruned:
        log(f"Pruned {pruned} stale entries from state")


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    global MIN_REELS_FOR_BASELINE, WINNER_WINDOW_DAYS, SCRAPE_DAYS

    parser = argparse.ArgumentParser()
    parser.add_argument("--since", metavar="YYYY-MM-DD",
                        help="surface winners posted on or after this date")
    args = parser.parse_args()

    if args.since:
        since = datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        window = (_now - since).days + 1
        WINNER_WINDOW_DAYS     = window
        SCRAPE_DAYS            = window
        MIN_REELS_FOR_BASELINE = 3
        log(f"--since {args.since}: window={window}d, min_reels_baseline=3")

    log("=" * 60)
    log(f"IG research pipeline — {TODAY}")

    handles    = load_handles()
    log(f"Handles ({len(handles)}): {handles}")

    raw_items  = scrape_apify(handles)
    handle_map = {h.lower(): h for h in handles}
    stripped   = [s for item in raw_items if (s := strip_fields(item, handle_map))]
    log(f"Stripped to {len(stripped)} reels")

    state = load_state()
    for post in stripped:
        upsert_post(state, post)
    save_state(state)
    log(f"State: {len(state['posts'])} total tracked posts")

    baselines, skipped = compute_baselines(state)
    log(f"Baselines computed for {len(baselines)} handle(s), skipped {len(skipped)}")

    winners_this_run = detect_winners(state, baselines)
    log(f"New winners this run: {len(winners_this_run)}")

    analyzed = []
    for w in winners_this_run:
        log(f"Analyzing {w['url']} …")
        analyzed.append(analyze_winner(w, state))

    save_state(state)

    write_json(analyzed, baselines, skipped)
    write_md(analyzed, baselines, skipped)
    total_csv = write_csv(analyzed)

    notion_urls = []
    if analyzed and NOTION_API_KEY:
        log("Pushing winners to Notion…")
        notion_urls = push_winners(analyzed, TODAY)
    elif analyzed:
        log("Skipping Notion push — NOTION_API_KEY not set")

    prune_state(state)
    save_state(state)

    viral_n = sum(1 for w in analyzed if w["viral_flag"])
    print(
        f"\n{len(analyzed)} new winners ({viral_n} viral, threshold 8x) | "
        f"scanned: {len(baselines)}, skipped low-volume: {len(skipped)} | "
        f"csv total rows: {total_csv} | notion pages: {len(notion_urls)}"
    )


if __name__ == "__main__":
    main()
