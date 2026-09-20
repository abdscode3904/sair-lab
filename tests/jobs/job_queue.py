from __future__ import annotations

from queue import Queue, Empty
from threading import Lock
from typing import Optional


class JobQueue:
    """
    In-memory job queue for Sair Lab.

    V1:
        Python Queue + Worker thread

    Later:
        Redis / Celery / cloud queue if scale requires it.
    """

    def __init__(self):
        self._queue: Queue[str] = Queue()
        self._queued_jobs: set[str] = set()
        self._lock = Lock()

    def add(self, job_id: str) -> bool:
        """
        Add a job to the queue.

        Returns:
            True  -> added
            False -> already queued
        """

        with self._lock:

            if job_id in self._queued_jobs:
                return False

            self._queued_jobs.add(job_id)
            self._queue.put(job_id)

            return True

    def get(
        self,
        timeout: Optional[float] = None,
    ) -> Optional[str]:
        """
        Get the next job from the queue.
        """

        try:
            job_id = self._queue.get(
                timeout=timeout
            )

        except Empty:
            return None

        with self._lock:
            self._queued_jobs.discard(job_id)

        return job_id

    def task_done(self) -> None:
        """
        Mark the current queue task as complete.
        """

        self._queue.task_done()

    def wait_until_empty(self) -> None:
        """
        Wait until all queued jobs are processed.
        """

        self._queue.join()

    def size(self) -> int:
        """
        Return approximate number of queued jobs.
        """

        return self._queue.qsize()

    def is_queued(
        self,
        job_id: str,
    ) -> bool:
        """
        Check whether a job is currently waiting
        in the queue.
        """

        with self._lock:
            return job_id in self._queued_jobs

    def empty(self) -> bool:
        return self._queue.empty()