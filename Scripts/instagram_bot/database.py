"""SQLite layer — tracks every post ever seen, view count history, and analysis state.

Schema design:
  posts          — one row per post, updated when views grow
  view_snapshots — time-series of view counts per post (for growth tracking)

This gives us:
  • Zero repeats: any post_id already in DB is skipped for re-analysis
  • Late-bloomer detection: posts that crossed 10K views AFTER first seen
  • Growth velocity: can see which posts are accelerating fastest
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from config import OUTPUT_DIR

DB_PATH = OUTPUT_DIR / "posts.db"


def init_db():
    with _conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS posts (
                post_id         TEXT PRIMARY KEY,
                username        TEXT NOT NULL,
                url             TEXT,
                thumbnail       TEXT,
                caption         TEXT,
                hashtags        TEXT,
                is_video        INTEGER DEFAULT 0,
                posted_at       TEXT,
                first_seen_at   TEXT NOT NULL,
                last_checked_at TEXT,
                views_first     INTEGER DEFAULT 0,
                views_latest    INTEGER DEFAULT 0,
                likes_latest    INTEGER DEFAULT 0,
                comments_latest INTEGER DEFAULT 0,
                analyzed        INTEGER DEFAULT 0,
                crm_date        TEXT
            );

            CREATE TABLE IF NOT EXISTS view_snapshots (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id     TEXT NOT NULL,
                checked_at  TEXT NOT NULL,
                views       INTEGER DEFAULT 0,
                FOREIGN KEY (post_id) REFERENCES posts(post_id)
            );

            CREATE INDEX IF NOT EXISTS idx_posts_analyzed ON posts(analyzed);
            CREATE INDEX IF NOT EXISTS idx_posts_views ON posts(views_latest DESC);
            CREATE INDEX IF NOT EXISTS idx_posts_posted ON posts(posted_at DESC);
        """)


@contextmanager
def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def upsert_posts(posts: list[dict[str, Any]]) -> tuple[int, int]:
    """Insert new posts; update view counts on existing ones.
    Returns (new_count, updated_count).
    """
    now = datetime.now(timezone.utc).isoformat()
    new_count = updated_count = 0

    with _conn() as c:
        for p in posts:
            existing = c.execute(
                "SELECT post_id, views_latest FROM posts WHERE post_id = ?",
                (p["post_id"],),
            ).fetchone()

            if existing is None:
                c.execute(
                    """INSERT INTO posts
                       (post_id, username, url, thumbnail, caption, hashtags,
                        is_video, posted_at, first_seen_at, last_checked_at,
                        views_first, views_latest, likes_latest, comments_latest)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        p["post_id"], p["username"], p["url"], p["thumbnail"],
                        p["caption"], p["hashtags"], int(p["is_video"]),
                        p["posted_at"], now, now,
                        p["views"], p["views"], p["likes"], p["comments"],
                    ),
                )
                new_count += 1
            else:
                c.execute(
                    """UPDATE posts SET
                        views_latest = ?, likes_latest = ?, comments_latest = ?,
                        last_checked_at = ?
                       WHERE post_id = ?""",
                    (p["views"], p["likes"], p["comments"], now, p["post_id"]),
                )
                updated_count += 1

            # always snapshot the view count
            c.execute(
                "INSERT INTO view_snapshots (post_id, checked_at, views) VALUES (?,?,?)",
                (p["post_id"], now, p["views"]),
            )

    return new_count, updated_count


def get_posts_to_recheck(days: int = 7) -> list[dict]:
    """Return posts seen in the last `days` days that haven't been checked today.
    Used to catch late-blooming viral videos.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).isoformat()

    with _conn() as c:
        rows = c.execute(
            """SELECT * FROM posts
               WHERE first_seen_at >= ?
                 AND (last_checked_at IS NULL OR last_checked_at < ?)
                 AND is_video = 1
               ORDER BY views_latest DESC""",
            (cutoff, today_start),
        ).fetchall()
    return [dict(r) for r in rows]


def update_views(post_id: str, views: int, likes: int, comments: int):
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as c:
        c.execute(
            "UPDATE posts SET views_latest=?, likes_latest=?, comments_latest=?, last_checked_at=? WHERE post_id=?",
            (views, likes, comments, now, post_id),
        )
        c.execute(
            "INSERT INTO view_snapshots (post_id, checked_at, views) VALUES (?,?,?)",
            (post_id, now, views),
        )


def get_qualifying_unanalyzed(min_views: int, limit: int) -> list[dict]:
    """Return top `limit` video posts with ≥ min_views that haven't been analyzed yet."""
    with _conn() as c:
        rows = c.execute(
            """SELECT * FROM posts
               WHERE is_video = 1
                 AND views_latest >= ?
                 AND analyzed = 0
               ORDER BY views_latest DESC
               LIMIT ?""",
            (min_views, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def mark_analyzed(post_ids: list[str], crm_date: str):
    with _conn() as c:
        for pid in post_ids:
            c.execute(
                "UPDATE posts SET analyzed=1, crm_date=? WHERE post_id=?",
                (crm_date, pid),
            )


def already_seen(post_id: str) -> bool:
    with _conn() as c:
        row = c.execute(
            "SELECT 1 FROM posts WHERE post_id = ?", (post_id,)
        ).fetchone()
    return row is not None
