"""RQ worker entrypoint.

Run with ``python -m socialposter.worker``. Connects to ``REDIS_URL`` and
listens on the ``socialposter`` queue. The worker pre-loads a Flask app
(scheduler skipped) so every job has a ready app context.
"""

from __future__ import annotations

import logging
import os
import sys

logger = logging.getLogger("socialposter")


def main() -> int:
    os.environ.setdefault("SOCIALPOSTER_SKIP_SCHEDULER", "1")

    from socialposter.core import jobs, queue as task_queue

    if not task_queue.is_enabled():
        sys.stderr.write(
            "REDIS_URL is not set — refusing to start a worker.\n"
            "Set REDIS_URL or run the web server in inline mode.\n"
        )
        return 2

    # Warm the worker-side Flask app once so the first job doesn't pay for it.
    jobs._get_app()

    # RQ's default Worker uses os.fork(), which Windows doesn't have. Fall
    # back to SimpleWorker (in-process job execution) on Windows.
    if sys.platform == "win32":
        from rq import SimpleWorker as WorkerClass
    else:
        from rq import Worker as WorkerClass

    connection = task_queue.get_connection()
    queue = task_queue.get_queue()
    logger.info("Starting RQ worker on queue %r (%s)", queue.name, WorkerClass.__name__)
    WorkerClass([queue], connection=connection).work(with_scheduler=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
