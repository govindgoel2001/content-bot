"""Main pipeline — Scrape → Qualify (with dedup) → Analyze → CRM.

Run once:   python main.py
Run daemon: python main.py --daemon   (fires at 22:00 PT every day)
"""

import argparse
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

from config import OUTPUT_DIR

LOG_PATH = OUTPUT_DIR / "run.log"


def _log(msg: str):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    with open(LOG_PATH, "a") as f:
        f.write(line + "\n")


def run_pipeline():
    _log("=" * 60)
    _log("Pipeline started")

    # ── load competitor list ───────────────────────────────────────────────────
    competitors_path = Path(__file__).parent / "competitors.json"
    with open(competitors_path) as f:
        cfg = json.load(f)
    handles = cfg.get("handles", [])

    if not handles or handles == [
        "example_competitor_1", "example_competitor_2", "example_competitor_3"
    ]:
        _log("ERROR: Please fill in real competitor handles in competitors.json first.")
        sys.exit(1)

    _log(f"Competitors ({len(handles)}): {handles}")

    # ── Stage 1: Scrape last 24h ───────────────────────────────────────────────
    _log("Stage 1: Scraping Instagram (last 24h only)...")
    from scraper import InstagramScraper
    scraper = InstagramScraper()
    new_posts = scraper.run(handles)
    _log(f"Stage 1 complete: {len(new_posts)} new post(s) fetched")

    # ── Stage 2: Qualify, re-check late bloomers, deduplicate ─────────────────
    _log("Stage 2: Qualifying + late-bloomer re-check...")
    from qualifier import qualify_and_rank, enrich_db_row
    top_db_rows = qualify_and_rank(new_posts, scraper.L)

    if not top_db_rows:
        _log("No unanalyzed posts with ≥10,000 views today. Skipping analysis.")
        _log("(All qualifying posts may have already been analyzed, or none hit the threshold yet.)")
        _log("=" * 60)
        return None

    top_posts = [enrich_db_row(r) for r in top_db_rows]
    _log(f"Stage 2 complete: {len(top_posts)} post(s) to analyze")

    # ── Stage 3: Claude AI analysis + 5 spins ─────────────────────────────────
    _log("Stage 3: Running Claude analysis...")
    from analyzer import analyze_all
    analyzed = analyze_all(top_posts)
    _log("Stage 3 complete")

    # ── Stage 4: Excel CRM ────────────────────────────────────────────────────
    _log("Stage 4: Generating Excel CRM...")
    from crm import generate_crm
    crm_path = generate_crm(analyzed)

    # Mark posts as analyzed in DB so they never repeat
    from database import mark_analyzed
    crm_date = datetime.now().strftime("%Y-%m-%d")
    mark_analyzed([p["post_id"] for p in top_posts], crm_date)

    _log(f"Pipeline complete. CRM saved: {crm_path}")
    _log("=" * 60)
    return crm_path


def main():
    parser = argparse.ArgumentParser(description="Instagram Content Bot — @gobi_automates")
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run as background scheduler (fires at 22:00 PT daily)",
    )
    args = parser.parse_args()

    if args.daemon:
        from scheduler import start_daemon
        start_daemon(run_pipeline)
    else:
        try:
            run_pipeline()
        except Exception:
            _log("FATAL ERROR:")
            _log(traceback.format_exc())
            sys.exit(1)


if __name__ == "__main__":
    main()
