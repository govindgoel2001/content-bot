"""Push scored Instagram outlier winners to a Notion database.

Required env vars:
  NOTION_API_KEY       — from https://www.notion.so/my-integrations
  NOTION_WINNERS_DB_ID — database ID for the IG Outlier Winners board

Notion DB properties to create before first run:
  Name (title), Handle (select), Views (number), Score (number),
  Viral (checkbox), Posted (date), Run Date (date), Reel URL (url)
"""

import os

import requests

NOTION_API_KEY    = os.environ.get("NOTION_API_KEY", "")
NOTION_WINNERS_DB = os.environ.get("NOTION_WINNERS_DB_ID", "")
NOTION_VERSION    = "2022-06-28"
BASE_URL          = "https://api.notion.com/v1"


def _headers() -> dict:
    return {
        "Authorization":  f"Bearer {NOTION_API_KEY}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type":   "application/json",
    }


def _rich_text(content: str) -> list:
    return [{"type": "text", "text": {"content": (content or "")[:2000]}}]


def push_winner(winner: dict, run_date: str) -> str:
    """Push a single analyzed winner to Notion. Returns the created page URL."""
    if not NOTION_API_KEY or not NOTION_WINNERS_DB:
        raise RuntimeError("NOTION_API_KEY and NOTION_WINNERS_DB_ID must be set")

    handle = winner["handle"]
    score  = winner["outlier_score"]
    viral  = winner["viral_flag"]
    angles = winner.get("spin_angles", [])

    properties = {
        "Name":     {"title": _rich_text(f"@{handle} — {score:.1f}x{' VIRAL' if viral else ''}")},
        "Handle":   {"select": {"name": handle}},
        "Views":    {"number": winner["views"]},
        "Score":    {"number": score},
        "Viral":    {"checkbox": viral},
        "Posted":   {"date": {"start": winner["posted_at"][:10]}},
        "Run Date": {"date": {"start": run_date}},
        "Reel URL": {"url": winner["url"]},
    }

    children = [
        {
            "object": "block", "type": "callout",
            "callout": {
                "rich_text": _rich_text(
                    f"@{handle} · {winner['views']:,} views · {score:.2f}x"
                    + ("  — VIRAL" if viral else "")
                ),
                "icon":  {"emoji": "🚨" if viral else "🔥"},
                "color": "red_background" if viral else "yellow_background",
            },
        },
        {
            "object": "block", "type": "heading_3",
            "heading_3": {"rich_text": _rich_text("Why it worked")},
        },
        {
            "object": "block", "type": "paragraph",
            "paragraph": {"rich_text": _rich_text(winner.get("why_it_worked", ""))},
        },
        {"object": "block", "type": "divider", "divider": {}},
        {
            "object": "block", "type": "heading_3",
            "heading_3": {"rich_text": _rich_text("Spin angles for @gobi_automates")},
        },
    ]

    for angle in angles[:5]:
        if angle:
            children.append({
                "object": "block", "type": "numbered_list_item",
                "numbered_list_item": {"rich_text": _rich_text(angle)},
            })

    payload = {
        "parent":     {"database_id": NOTION_WINNERS_DB},
        "properties": properties,
        "children":   children,
    }

    resp = requests.post(f"{BASE_URL}/pages", headers=_headers(), json=payload, timeout=30)
    if resp.status_code >= 400:
        raise RuntimeError(f"Notion API {resp.status_code}: {resp.text}")
    return resp.json().get("url", "")


def push_winners(analyzed: list[dict], run_date: str) -> list[str]:
    """Push all analyzed winners to Notion. Returns list of created page URLs."""
    urls = []
    for w in analyzed:
        try:
            page_url = push_winner(w, run_date)
            print(f"[Notion] Pushed: {page_url}")
            urls.append(page_url)
        except Exception as e:
            print(f"[Notion] FAILED {w['url']}: {e}")
    return urls
