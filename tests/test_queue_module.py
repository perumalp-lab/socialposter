"""Tests for the queue module — connection, enqueue against fakeredis."""

from __future__ import annotations

import pytest


def test_is_enabled_false_without_redis_url(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    from socialposter.core import queue as task_queue
    task_queue.reset_for_testing(None, None)
    assert task_queue.is_enabled() is False


def test_is_enabled_true_with_redis_url(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://example:6379/0")
    from socialposter.core import queue as task_queue
    task_queue.reset_for_testing(None, None)
    assert task_queue.is_enabled() is True
    task_queue.reset_for_testing(None, None)


def test_enqueue_against_fakeredis(monkeypatch):
    """A real RQ enqueue against a fakeredis backend lands a job on the queue."""
    fakeredis = pytest.importorskip("fakeredis")
    from rq import Queue

    fake = fakeredis.FakeStrictRedis()
    queue = Queue("socialposter", connection=fake)

    from socialposter.core import queue as task_queue
    task_queue.reset_for_testing(connection=fake, queue=queue)

    def _payload(x, y):
        return x + y

    monkeypatch.setenv("REDIS_URL", "redis://fake:6379/0")
    job = task_queue.enqueue(_payload, 2, 3)

    assert job is not None
    assert queue.count == 1
    task_queue.reset_for_testing(None, None)
