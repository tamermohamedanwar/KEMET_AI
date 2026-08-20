"""
Kemet AI V4.6 Follow-up Worker

One-shot worker for due CRM follow-ups.

Safety:
- Does not send external messages.
- Does not approve follow-ups.
- Does not complete follow-ups.
- Only prepares due follow-ups for the Human Review Queue.
- Safe to run repeatedly because the execution engine is idempotent.
"""

import os
import sys

from app import create_app


def main():
    try:
        limit = int(os.getenv("FOLLOW_UP_WORKER_LIMIT", "50"))
    except (TypeError, ValueError):
        limit = 50

    limit = max(1, min(limit, 200))

    app = create_app()

    with app.app_context():
        from app.services.automation_service import automation_service

        result = automation_service.execute_due_follow_ups(
            limit=limit
        )

        if not result.get("success"):
            print("FOLLOW-UP WORKER: FAILED")
            print(result)
            return 1

        print("========================================")
        print("KEMET AI V4.6 FOLLOW-UP WORKER")
        print("STATUS:", result.get("status"))
        print("CHECKED:", result.get("checked", 0))
        print("PROCESSED:", result.get("processed", 0))
        print("SKIPPED:", result.get("skipped", 0))
        print("HUMAN REVIEW REQUIRED: YES")
        print("EXTERNAL MESSAGE SENT: NO")
        print("========================================")

        return 0


if __name__ == "__main__":
    sys.exit(main())
