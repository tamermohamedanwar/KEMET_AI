import argparse
import logging
import os
import signal
import sys
import time

from app import create_app
from app.services.automation_service import automation_service


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL = 60
DEFAULT_LIMIT = 50


def execute_once(limit=DEFAULT_LIMIT):
    app = create_app()

    with app.app_context():
        result = automation_service.execute_due_follow_ups(limit=limit)

    if not result.get("success"):
        logger.error("Follow-up execution failed: %s", result)
        return 1

    logger.info(
        "Follow-up cycle complete | status=%s checked=%s processed=%s skipped=%s",
        result.get("status"),
        result.get("checked", 0),
        result.get("processed", 0),
        result.get("skipped", 0),
    )

    logger.info("HUMAN REVIEW REQUIRED: YES")
    logger.info("EXTERNAL MESSAGE SENT: NO")

    return 0


def run_scheduler(interval=DEFAULT_INTERVAL, limit=DEFAULT_LIMIT):
    running = True

    def stop_handler(signum, frame):
        nonlocal running
        logger.info("Shutdown signal received: %s", signum)
        running = False

    signal.signal(signal.SIGINT, stop_handler)
    signal.signal(signal.SIGTERM, stop_handler)

    logger.info("========================================")
    logger.info("KEMET AI V4.7 FOLLOW-UP SCHEDULER")
    logger.info("INTERVAL: %s seconds", interval)
    logger.info("LIMIT: %s", limit)
    logger.info("HUMAN REVIEW GATE: ENABLED")
    logger.info("EXTERNAL MESSAGE SENDING: DISABLED")
    logger.info("========================================")

    while running:
        started = time.monotonic()

        try:
            execute_once(limit=limit)
        except Exception:
            logger.exception("Unhandled follow-up scheduler error")

        elapsed = time.monotonic() - started
        sleep_for = max(0, interval - elapsed)

        if running and sleep_for:
            time.sleep(sleep_for)

    logger.info("V4.7 scheduler stopped cleanly.")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Kemet AI CRM follow-up scheduler"
    )

    parser.add_argument(
        "--once",
        action="store_true",
        help="Execute one follow-up cycle and exit.",
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=int(
            os.getenv(
                "KEMET_FOLLOWUP_INTERVAL",
                DEFAULT_INTERVAL,
            )
        ),
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=int(
            os.getenv(
                "KEMET_FOLLOWUP_LIMIT",
                DEFAULT_LIMIT,
            )
        ),
    )

    args = parser.parse_args()

    interval = max(5, min(args.interval, 3600))
    limit = max(1, min(args.limit, 200))

    if args.once:
        return execute_once(limit=limit)

    return run_scheduler(
        interval=interval,
        limit=limit,
    )


if __name__ == "__main__":
    sys.exit(main())
