"""Stage 1 — Scrape: uses Apify Instagram scraper (no IG login needed).

Runs all competitor accounts in a single Apify actor call.
Free tier: $5 credit covers months of daily runs at this scale.
"""

import time
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from config import APIFY_API_KEY, SCRAPE_WINDOW_HOURS

ACTOR_ID = "apify~instagram-scraper"
BASE_URL  = "https://api.apify.com/v2"


class InstagramScraper:
    def __init__(self):
        self.cl = None  # kept for qualifier.py compatibility

    def run(self, handles: list[str]) -> list[dict[str, Any]]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=SCRAPE_WINDOW_HOURS)
        urls   = [f"https://www.instagram.com/{h}/" for h in handles]

        print(f"[Scraper] Starting Apify run for: {handles}")
        resp = requests.post(
            f"{BASE_URL}/acts/{ACTOR_ID}/runs",
            params={"token": APIFY_API_KEY},
            json={"directUrls": urls, "resultsType": "posts", "resultsLimit": 20,
                  "proxy": {"useApifyProxy": True}},
            timeout=30,
        )
        resp.raise_for_status()
        run_data   = resp.json()["data"]
        run_id     = run_data["id"]
        dataset_id = run_data["defaultDatasetId"]

        # Poll until done
        while True:
            status = requests.get(
                f"{BASE_URL}/actor-runs/{run_id}",
                params={"token": APIFY_API_KEY},
                timeout=15,
            ).json()["data"]["status"]
            print(f"[Scraper] Apify status: {status}")
            if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                break
            time.sleep(5)

        if status != "SUCCEEDED":
            print(f"[Scraper] Apify run ended with status: {status}")
            return []

        items = requests.get(
            f"{BASE_URL}/datasets/{dataset_id}/items",
            params={"token": APIFY_API_KEY, "clean": "true"},
            timeout=30,
        ).json()

        handle_lower = {h.lower(): h for h in handles}
        all_posts: list[dict[str, Any]] = []

        for item in items:
            owner  = (item.get("ownerUsername") or "").lower()
            handle = handle_lower.get(owner, owner)

            ts = item.get("timestamp", "")
            try:
                post_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                post_time = datetime.now(timezone.utc)

            if post_time < cutoff:
                continue

            all_posts.append(_normalize(item, handle))

        counts = {}
        for p in all_posts:
            counts[p["username"]] = counts.get(p["username"], 0) + 1
        for h, n in counts.items():
            print(f"[Scraper] @{h} → {n} new post(s) in last {SCRAPE_WINDOW_HOURS}h")

        print(f"[Scraper] Total new posts this window: {len(all_posts)}")
        return all_posts


def _normalize(item: dict, handle: str) -> dict[str, Any]:
    is_video  = item.get("type") == "Video"
    shortcode = item.get("shortCode", "")
    return {
        "post_id":   str(item.get("id") or shortcode),
        "shortcode": shortcode,
        "username":  handle,
        "url":       item.get("url") or f"https://www.instagram.com/p/{shortcode}/",
        "thumbnail": item.get("displayUrl", ""),
        "caption":   (item.get("caption") or "")[:2000],
        "hashtags":  " ".join(f"#{t}" for t in (item.get("hashtags") or [])),
        "views":     item.get("videoViewCount") or 0,
        "likes":     item.get("likesCount") or 0,
        "comments":  item.get("commentsCount") or 0,
        "is_video":  is_video,
        "is_reel":   is_video,
        "posted_at": item.get("timestamp", ""),
        "typename":  "GraphVideo" if is_video else "GraphImage",
    }
