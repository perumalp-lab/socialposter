"""Tests for socialposter.core.jobs (RQ job functions)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _reuse_test_app(app):
    """Make jobs._get_app() return the test app instead of building a new one."""
    from socialposter.core import jobs

    jobs.reset_app_for_testing(app)
    yield
    jobs.reset_app_for_testing(None)


@pytest.fixture
def schedule(db, test_user):
    from socialposter.web.models import (
        PostHistory, PublishedPost, ScheduleLog, ScheduledPost,
    )

    s = ScheduledPost(
        user_id=test_user.id,
        name="Daily LinkedIn",
        platforms=["linkedin"],
        text="Hello world",
        media=[],
        overrides={},
        interval_minutes=60,
        next_run_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1),
    )
    db.session.add(s)
    db.session.commit()
    yield s
    # Clean up rows the job may have written — SQLite reuses IDs after
    # delete, so leftover history would leak across tests.
    PostHistory.query.filter_by(schedule_id=s.id).delete()
    ScheduleLog.query.filter_by(schedule_id=s.id).delete()
    PublishedPost.query.filter_by(user_id=s.user_id).delete()
    db.session.delete(s)
    db.session.commit()


def _fake_publish(success: bool):
    from socialposter.platforms.base import PostResult

    return PostResult(
        success=success,
        platform="linkedin",
        post_id="abc123" if success else None,
        post_url="https://linkedin.com/posts/abc123" if success else None,
        error_message=None if success else "boom",
    )


def test_publish_scheduled_post_records_history_and_log(schedule, db):
    """A successful publish writes PostHistory + PublishedPost + ScheduleLog."""
    from socialposter.core import jobs
    from socialposter.web.models import PostHistory, PublishedPost, ScheduleLog

    with patch("socialposter.core.publisher._publish_one",
               return_value=_fake_publish(True)):
        result = jobs.publish_scheduled_post(schedule.id, "linkedin")

    assert result["success"] is True
    assert result["platform"] == "linkedin"
    assert result["post_id"] == "abc123"

    assert PostHistory.query.filter_by(schedule_id=schedule.id).count() == 1
    assert ScheduleLog.query.filter_by(schedule_id=schedule.id).count() == 1
    log = ScheduleLog.query.filter_by(schedule_id=schedule.id).first()
    assert log.results[0]["platform"] == "linkedin"
    assert log.results[0]["success"] is True

    pub = PublishedPost.query.filter_by(user_id=schedule.user_id).first()
    assert pub is not None
    assert pub.platform_post_id == "abc123"


def test_publish_scheduled_post_raises_on_failure(schedule, db):
    """A failed publish raises so RQ retries it, but still records history."""
    from socialposter.core import jobs
    from socialposter.web.models import PostHistory, ScheduleLog

    with patch("socialposter.core.publisher._publish_one",
               return_value=_fake_publish(False)):
        with pytest.raises(RuntimeError, match="linkedin publish failed"):
            jobs.publish_scheduled_post(schedule.id, "linkedin")

    history = PostHistory.query.filter_by(schedule_id=schedule.id).first()
    assert history is not None
    assert history.success is False
    assert history.error_message == "boom"
    assert ScheduleLog.query.filter_by(schedule_id=schedule.id).count() == 1


def test_publish_scheduled_post_skips_disabled(schedule, db):
    """Disabled schedules return a skip dict without publishing."""
    from socialposter.core import jobs

    schedule.enabled = False
    db.session.commit()

    with patch("socialposter.core.publisher._publish_one") as publish_mock:
        result = jobs.publish_scheduled_post(schedule.id, "linkedin")

    publish_mock.assert_not_called()
    assert result == {"skipped": True, "reason": "not_found_or_disabled"}


def test_publish_scheduled_post_skips_unknown_platform(schedule, db):
    """An unknown platform name returns a skip dict without publishing."""
    from socialposter.core import jobs

    with patch("socialposter.core.publisher._publish_one") as publish_mock:
        result = jobs.publish_scheduled_post(schedule.id, "myspace")

    publish_mock.assert_not_called()
    assert result == {"skipped": True, "reason": "platform_unknown"}
