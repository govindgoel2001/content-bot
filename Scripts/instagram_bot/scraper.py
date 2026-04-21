"""Stage 1 — Scrape: uses Instaloader (free, no API key) to pull recent posts.

Strategy: only fetch posts from the LAST 24 HOURS per competitor account.
The database layer handles dedup and late-bloomer re-checking separately.

Requires a throwaway Instagram account for reliable rate limits.
Set IG_USERNAME / IG_PASSWORD in .env, or leave blank for anonymous mode
(anonymous mode is heavily rate-limited by Instagram).
"""

import os
import time
import random
from datetime import datetime, timedelta, timezone
from typing import Any

import instaloader

from config import IG_USERNAME, IG_PASSWORD, SCRAPE_WINDOW_HOURS


class InstagramScraper:
    def __init__(self):
        self.L = instaloader.Instaloader(
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            quiet=True,
        )
        self._login()

    def _login(self):
        if IG_USERNAME and IG_PASSWORD:
            try:
                self.L.login(IG_USERNAME, IG_PASSWORD)
                print(f"[Scraper] Logged in as @{IG_USERNAME}")
            except Exception as e:
                print(f"[Scraper] Login failed ({e}) — falling back to anonymous mode")
        else:
            print("[Scraper] No IG credentials set — running anonymous (may be rate-limited)")

    def scrape_account(self, handle: str, since_hours: int = SCRAPE_WINDOW_HOURS) -> list[dict[str, Any]]:
        """Return posts from `handle` published in the last `since_hours` hours."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)
        posts = []

        try:
            profile = instaloader.Profile.from_username(self.L.context, handle)
        except instaloader.exceptions.ProfileNotExistsException:
            print(f"[Scraper] @{handle} not found — skipping")
            return []
        except Exception as e:
            print(f"[Scraper] Error loading @{handle}: {e}")
            return []

        for post in profile.get_posts():
            post_time = post.date_utc.replace(tzinfo=timezone.utc)
            if post_time < cutoff:
                break  # posts are chronological newest-first; stop early

            posts.append(_normalize_instaloader_post(post, handle))

        print(f"[Scraper] @{handle} → {len(posts)} new post(s) in last {since_hours}h")
        # polite delay between accounts (1–3s)
        time.sleep(random.uniform(1, 3))
        return posts

    def run(self, handles: list[str]) -> list[dict[str, Any]]:
        all_posts: list[dict[str, Any]] = []
        for handle in handles:
            all_posts.extend(self.scrape_account(handle))
        print(f"[Scraper] Total new posts this window: {len(all_posts)}")
        return all_posts


def _normalize_instaloader_post(post, handle: str) -> dict[str, Any]:
    is_video = post.is_video
    return {
        "post_id": str(post.mediaid),
        "shortcode": post.shortcode,
        "username": handle,
        "url": f"https://www.instagram.com/p/{post.shortcode}/",
        "thumbnail": post.url,
        "caption": (post.caption or "")[:2000],
        "hashtags": " ".join(f"#{t}" for t in post.caption_hashtags),
        "views": post.video_view_count if is_video else 0,
        "likes": post.likes,
        "comments": post.comments,
        "is_video": is_video,
        "is_reel": post.is_video,   # Instaloader doesn't distinguish Reels vs regular video; both count
        "posted_at": post.date_utc.replace(tzinfo=timezone.utc).isoformat(),
        "typename": post.typename,  # "GraphVideo", "GraphImage", "GraphSidecar"
    }
