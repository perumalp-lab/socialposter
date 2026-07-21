"""E2E helper — create a user and a due ScheduledPost, then dispatch.

Used by manual end-to-end testing of the Redis queue path. Reads DATABASE_URL
and REDIS_URL from the environment and prints what it did.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone


def main() -> None:
    os.environ.setdefault("SOCIALPOSTER_SKIP_SCHEDULER", "1")

    from socialposter.web.app import create_app
    from socialposter.web.models import (
        PostHistory, ScheduleLog, ScheduledPost, User, db,
    )
    from socialposter.core import scheduler as sched_mod
    from socialposter.core import queue as task_queue

    app = create_app()
    with app.app_context():
        # Seed a user
        user = User.query.filter_by(email="e2e@example.com").first()
        if not user:
            user = User(email="e2e@example.com", display_name="E2E", is_admin=True)
            user.set_password("e2e-pass")
            db.session.add(user)
            db.session.commit()
            print(f"created user id={user.id}")
        else:
            print(f"reusing user id={user.id}")

        # Seed a due schedule
        sched = ScheduledPost(
            user_id=user.id,
            name="E2E Test",
            platforms=["linkedin"],  # no real connection -> auth will fail
            text="hello from e2e",
            media=[],
            overrides={},
            interval_minutes=60,
            next_run_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=5),
        )
        db.session.add(sched)
        db.session.commit()
        sched_id = sched.id
        print(f"created schedule id={sched_id}")

        print(f"queue enabled? {task_queue.is_enabled()}")
        sched_mod._execute_due_posts(app)

        # Wait for the worker to process (RQ default poll = 1s; auth-fail is fast).
        deadline = time.time() + 15
        last_history_count = 0
        while time.time() < deadline:
            history_count = PostHistory.query.filter_by(schedule_id=sched_id).count()
            log_count = ScheduleLog.query.filter_by(schedule_id=sched_id).count()
            if history_count != last_history_count:
                print(f"  history={history_count}, schedule_logs={log_count}")
                last_history_count = history_count
            if history_count >= 1:
                break
            time.sleep(0.5)

        # Final summary
        history_rows = PostHistory.query.filter_by(schedule_id=sched_id).all()
        log_rows = ScheduleLog.query.filter_by(schedule_id=sched_id).all()
        print(f"\nFINAL: {len(history_rows)} history row(s), {len(log_rows)} schedule_log row(s)")
        for h in history_rows:
            print(f"  PostHistory: platform={h.platform} success={h.success} error={h.error_message[:80]!r}")
        for log in log_rows:
            print(f"  ScheduleLog: results={log.results}")


if __name__ == "__main__":
    main()
