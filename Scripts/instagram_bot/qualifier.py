"""Stage 2 — Qualify & Rank (smart version).

Two-pass strategy:
  Pass A — New posts (last 24h): upsert into DB; surface any that already
            have ≥10K views (instant viral).
  Pass B — Late-bloomer re-check: pull posts from DB seen in last 7 days
            that haven't been re-checked today; fetch fresh view counts from
            Instagram and update DB; surface any that just crossed 10K.

Final output: top N unanalyzed posts with ≥10K views, ranked by views.
No post is ever analyzed twice.
"""

import time
import random
from datetime import datetime, timezone
from typing import Any

from config import MIN_VIEWS, TOP_N
from database import (
    init_db,
    upsert_posts,
    get_posts_to_recheck,
    update_views,
    get_qualifying_unanalyzed,
)


def _fetch_fresh_views(cl, shortcode: str) -> tuple[int, int, int]:
    """Return (views, likes, comments) for a post by shortcode using instagrapi."""
    try:
        media = cl.media_info_by_shortcode(shortcode)
        views = media.view_count or 0
        return views, media.like_count or 0, media.comment_count or 0
    except Exception as e:
        print(f"  [re-check] Could not refresh {shortcode}: {e}")
        return -1, -1, -1


def _shortcode_from_url(url: str) -> str:
    return url.rstrip("/").split("/")[-1]


def qualify_and_rank(
    new_posts: list[dict[str, Any]],
    ig_client,
) -> list[dict[str, Any]]:
    init_db()

    # ── Pass A: ingest today's new posts ──────────────────────────────────────
    new_count, updated_count = upsert_posts(new_posts)
    print(
        f"[Qualifier] Pass A — {new_count} new posts inserted, "
        f"{updated_count} existing posts updated"
    )

    # ── Pass B: re-check posts from last 7 days for view growth ───────────────
    stale = get_posts_to_recheck(days=7)
    print(f"[Qualifier] Pass B — re-checking {len(stale)} posts for late-bloomer growth")

    for p in stale:
        sc = _shortcode_from_url(p["url"])
        views, likes, comments = _fetch_fresh_views(ig_client, sc)
        if views >= 0:
            old_views = p["views_latest"]
            update_views(p["post_id"], views, likes, comments)
            if views != old_views:
                delta = views - old_views
                sign = "+" if delta >= 0 else ""
                print(f"  @{p['username']} {sc}: {old_views:,} → {views:,} ({sign}{delta:,})")
        time.sleep(random.uniform(0.5, 1.5))

    # ── Select top N unanalyzed posts ≥ MIN_VIEWS ─────────────────────────────
    top = get_qualifying_unanalyzed(min_views=MIN_VIEWS, limit=TOP_N)
    print(
        f"[Qualifier] {len(top)} unanalyzed post(s) with ≥{MIN_VIEWS:,} views "
        f"(want top {TOP_N})"
    )

    for i, p in enumerate(top, 1):
        growth = p["views_latest"] - p["views_first"]
        print(
            f"  #{i}: @{p['username']} — {p['views_latest']:,} views "
            f"(+{growth:,} since first seen) | {p['url']}"
        )

    return top


def enrich_db_row(row: dict) -> dict:
    """Map DB column names to the field names expected by analyzer.py and crm.py."""
    likes = row.get("likes_latest", 0)
    comments = row.get("comments_latest", 0)
    views = row.get("views_latest", 0)
    total_eng = likes + comments
    eng_rate = round(total_eng / views * 100, 2) if views else 0

    return {
        "post_id": row["post_id"],
        "username": row["username"],
        "url": row["url"],
        "thumbnail": row.get("thumbnail", ""),
        "caption": row.get("caption", ""),
        "hashtags": row.get("hashtags", ""),
        "views": views,
        "views_growth": views - row.get("views_first", 0),
        "likes": likes,
        "comments": comments,
        "engagement_rate": eng_rate,
        "posted_at": row.get("posted_at", "")[:10],
        "is_video": bool(row.get("is_video")),
    }
