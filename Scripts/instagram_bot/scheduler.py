"""Daemon scheduler — fires run_pipeline() at 22:00 America/Los_Angeles every day.

Uses APScheduler so it respects PST/PDT transitions automatically.
The process must stay alive (e.g. via systemd, screen, or nohup).
"""

import logging
import signal
import sys
import time
import traceback
from datetime import datetime
from typing import Callable

import pytz
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

PT = pytz.timezone("America/Los_Angeles")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [scheduler] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def _job_wrapper(pipeline_fn: Callable):
    log.info("Cron trigger fired — starting pipeline...")
    try:
        result = pipeline_fn()
        log.info(f"Pipeline finished successfully. Output: {result}")
    except Exception:
        log.error("Pipeline failed:\n" + traceback.format_exc())


def start_daemon(pipeline_fn: Callable):
    scheduler = BlockingScheduler(timezone=PT)

    scheduler.add_job(
        func=_job_wrapper,
        args=[pipeline_fn],
        trigger=CronTrigger(hour=22, minute=0, timezone=PT),
        id="daily_instagram_bot",
        name="Instagram Content Bot — 10pm PT",
        replace_existing=True,
        misfire_grace_time=3600,  # run even if up to 1h late (e.g. after restart)
        coalesce=True,
    )

    now_pt = datetime.now(PT)
    next_run = scheduler.get_job("daily_instagram_bot").next_run_time
    log.info(f"Daemon started. Current PT time: {now_pt.strftime('%Y-%m-%d %H:%M %Z')}")
    log.info(f"Next run: {next_run.strftime('%Y-%m-%d %H:%M %Z')}")
    log.info("Press Ctrl+C to stop.")

    def _shutdown(sig, frame):
        log.info("Shutdown signal received — stopping scheduler.")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    scheduler.start()
