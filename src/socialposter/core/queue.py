"""Redis-backed RQ task queue.

If REDIS_URL is unset, queue access raises and callers fall back to in-process
execution (preserving the dev experience without Redis installed).
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger("socialposter")

QUEUE_NAME = "socialposter"

DEFAULT_RETRY_INTERVALS = [30, 120, 600]
DEFAULT_JOB_TIMEOUT = 300

_connection = None
_queue = None


def _redis_url() -> Optional[str]:
    return os.environ.get("REDIS_URL") or None


def is_enabled() -> bool:
    """True if a queue backend is configured."""
    return bool(_redis_url())


def get_connection():
    """Lazily build (and cache) the Redis connection. Raises if no REDIS_URL."""
    global _connection
    if _connection is not None:
        return _connection

    url = _redis_url()
    if not url:
        raise RuntimeError("REDIS_URL is not configured")

    from redis import Redis

    _connection = Redis.from_url(url)
    return _connection


def get_queue():
    """Return the RQ Queue, building it on first call."""
    global _queue
    if _queue is not None:
        return _queue

    from rq import Queue

    _queue = Queue(QUEUE_NAME, connection=get_connection())
    return _queue


def reset_for_testing(connection=None, queue=None) -> None:
    """Inject test doubles. Tests pass a fakeredis connection + sync RQ queue."""
    global _connection, _queue
    _connection = connection
    _queue = queue


def enqueue(func, *args, retry_intervals=None, **kwargs):
    """Enqueue ``func(*args, **kwargs)`` with default retry policy.

    Returns the RQ Job. Caller is expected to handle the case where queueing
    is unavailable (check ``is_enabled()`` first).
    """
    from rq import Retry

    intervals = retry_intervals if retry_intervals is not None else DEFAULT_RETRY_INTERVALS
    q = get_queue()
    return q.enqueue(
        func,
        *args,
        retry=Retry(max=len(intervals), interval=intervals),
        job_timeout=DEFAULT_JOB_TIMEOUT,
        **kwargs,
    )
