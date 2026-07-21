"""Tests for the queue dispatch path in core/scheduler.py."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest


@pytest.fixture
def schedule(db, test_user):
    """Create a ScheduledPost row that's already due."""
    from socialposter.web.models import ScheduledPost

    s = ScheduledPost(
        user_id=test_user.id,
        name="Daily LinkedIn",
        platforms=["linkedin", "twitter"],
        text="Hello world",
        media=[],
        overrides={},
        interval_minutes=60,
        next_run_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1),
    )
    db.session.add(s)
    db.session.commit()
    yield s
    db.session.delete(s)
    db.session.commit()


def test_claim_advances_next_run_at(app, schedule):
    """_claim_due_posts advances next_run_at exactly once per due row."""
    from socialposter.core.scheduler import _claim_due_posts

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    first = _claim_due_posts(now)
    first_ids = [s.id for s in first]
    second = _claim_due_posts(now)
    second_ids = [s.id for s in second]

    assert first_ids == [schedule.id]
    # Second claim sees no due rows because next_run_at was advanced.
    assert second_ids == []


def test_dispatch_enqueues_one_job_per_platform(app, schedule):
    """When the queue is enabled, _execute_due_posts enqueues one job per (schedule, platform)."""
    from socialposter.core import scheduler as sched_mod

    with patch("socialposter.core.queue.is_enabled", return_value=True), \
         patch("socialposter.core.queue.enqueue") as enqueue_mock:
        sched_mod._execute_due_posts(app)

    assert enqueue_mock.call_count == 2
    enqueued_args = [call.args for call in enqueue_mock.call_args_list]
    platform_names = sorted(a[2] for a in enqueued_args)
    assert platform_names == ["linkedin", "twitter"]
    assert all(a[1] == schedule.id for a in enqueued_args)


def test_dispatch_falls_back_inline_without_queue(app, schedule):
    """When the queue is disabled, _execute_due_posts calls publish_scheduled_post inline."""
    from socialposter.core import scheduler as sched_mod

    with patch("socialposter.core.queue.is_enabled", return_value=False), \
         patch("socialposter.core.jobs.publish_scheduled_post") as publish_mock:
        publish_mock.return_value = {"platform": "linkedin", "success": True}
        sched_mod._execute_due_posts(app)

    assert publish_mock.call_count == 2


def test_dispatch_skips_when_no_due_rows(app, db, test_user):
    """No due rows -> no enqueue calls."""
    from socialposter.core import scheduler as sched_mod

    with patch("socialposter.core.queue.is_enabled", return_value=True), \
         patch("socialposter.core.queue.enqueue") as enqueue_mock:
        sched_mod._execute_due_posts(app)

    enqueue_mock.assert_not_called()
