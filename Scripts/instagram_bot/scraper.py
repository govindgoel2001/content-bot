"""Stage 1 — Scrape: uses instagrapi (mobile API) to pull recent posts.

Strategy: only fetch posts from the LAST 24 HOURS per competitor account.
The database layer handles dedup and late-bloomer re-checking separately.
"""

import json
import time
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from instagrapi import Client
from instagrapi.exceptions import LoginRequired, UserNotFound, ClientError

from config import IG_USERNAME, IG_PASSWORD, SCRAPE_WINDOW_HOURS

SESSION_PATH = Path(__file__).parent / "output" / "ig_session.json"


class InstagramScraper:
    def __init__(self):
        self.cl = Client()
        self.cl.delay_range = [2, 5]  # polite delays between requests
        self._login()
        # Expose as .L for qualifier.py compatibility (unused with instagrapi but keeps interface intact)
        self.L = None

    def _login(self):
        SESSION_PATH.parent.mkdir(exist_ok=True)
        # Try saved session first
        if SESSION_PATH.exists():
            try:
                self.cl.load_settings(SESSION_PATH)
                self.cl.login(IG_USERNAME, IG_PASSWORD)
                print(f"[Scraper] Loaded saved session for @{IG_USERNAME}")
                self._save_session()
                return
            except Exception as e:
                print(f"[Scraper] Saved session invalid ({e}) — logging in fresh")

        # Fresh login
        try:
            self.cl.login(IG_USERNAME, IG_PASSWORD)
            self._save_session()
            print(f"[Scraper] Logged in as @{IG_USERNAME}")
        except Exception as e:
            raise RuntimeError(f"Instagram login failed: {e}")

    def _save_session(self):
        self.cl.dump_settings(SESSION_PATH)

    def scrape_account(self, handle: str, since_hours: int = SCRAPE_WINDOW_HOURS) -> list[dict[str, Any]]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)
        posts = []

        try:
            user_id = self.cl.user_id_from_username(handle)
            medias = self.cl.user_medias(user_id, amount=20)
        except UserNotFound:
            print(f"[Scraper] @{handle} not found — skipping")
            return []
        except Exception as e:
            print(f"[Scraper] Error loading @{handle}: {type(e).__name__}: {e}")
            return []

        for media in medias:
            post_time = media.taken_at.replace(tzinfo=timezone.utc) if media.taken_at.tzinfo is None else media.taken_at.astimezone(timezone.utc)
            if post_time < cutoff:
                continue  # instagrapi doesn't guarantee order; check all 20

            posts.append(_normalize_media(media, handle))

        print(f"[Scraper] @{handle} → {len(posts)} new post(s) in last {since_hours}h")
        time.sleep(random.uniform(1, 3))
        return posts

    def run(self, handles: list[str]) -> list[dict[str, Any]]:
        all_posts: list[dict[str, Any]] = []
        for handle in handles:
            all_posts.extend(self.scrape_account(handle))
        print(f"[Scraper] Total new posts this window: {len(all_posts)}")
        return all_posts


def _normalize_media(media, handle: str) -> dict[str, Any]:
    is_video = media.media_type == 2  # 1=photo, 2=video, 8=album
    shortcode = media.code or str(media.pk)
    caption = media.caption_text or ""
    hashtags = " ".join(f"#{tag}" for tag in (media.hashtags or []))
    posted_at = media.taken_at
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=timezone.utc)

    return {
        "post_id": str(media.pk),
        "shortcode": shortcode,
        "username": handle,
        "url": f"https://www.instagram.com/p/{shortcode}/",
        "thumbnail": str(media.thumbnail_url or ""),
        "caption": caption[:2000],
        "hashtags": hashtags,
        "views": media.view_count or 0,
        "likes": media.like_count or 0,
        "comments": media.comment_count or 0,
        "is_video": is_video,
        "is_reel": is_video,
        "posted_at": posted_at.isoformat(),
        "typename": "GraphVideo" if is_video else "GraphImage",
    }
