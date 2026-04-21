import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# ── Required ──────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

# ── Instagram login (strongly recommended — avoids rate-limiting) ─────────────
# Use a throwaway/burner account, not your main @gobi_automates account.
IG_USERNAME = os.getenv("IG_USERNAME", "")
IG_PASSWORD = os.getenv("IG_PASSWORD", "")

# ── Pipeline settings ─────────────────────────────────────────────────────────
MY_HANDLE        = "gobi_automates"
MIN_VIEWS        = 10_000      # minimum views to qualify a video
TOP_N            = 3           # top N videos to analyze each day
SPIN_COUNT       = 5           # spin variations per video
SCRAPE_WINDOW_HOURS = 24       # only fetch posts newer than this

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)
