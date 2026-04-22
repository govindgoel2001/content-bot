import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# ── Required ──────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
APIFY_API_KEY     = os.environ["APIFY_API_KEY"]

# ── Pipeline settings ─────────────────────────────────────────────────────────
MY_HANDLE           = "gobi_automates"
MIN_VIEWS           = 10_000
TOP_N               = 3
SPIN_COUNT          = 5
SCRAPE_WINDOW_HOURS = 24

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)
