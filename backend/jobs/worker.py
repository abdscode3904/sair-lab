from __future__ import annotations

import threading
from typing import Optional

from backend.jobs.job_queue import JobQueue
from backend.jobs.job_processor import JobProcessor


class JobWorker:
    """
    Sair Lab background job worker.

    Takes job IDs from JobQueue and sends them
    to JobProcessor for execution.
    """

    def __init__(
        self,
        job_queue: JobQueue,
        job_processor: JobProcessor,
    ):
        self.job_queue = job_queue
        self.job_processor = job_processor

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        self.last_result = None
        self.processed_count = 0
        self.failed_count = 0

    # ============================================================
    # START
    # ============================================================

    def start(self) -> None:
        """
        Start the worker in a background thread.
        """

        if self.is_running():
            return

        self._stop_event.clear()

        self._thread = threading.Thread(
            target=self._run,
            name="SairLab-JobWorker",
            daemon=True,
        )

        self._thread.start()

    # ============================================================
    # WORKER LOOP
    # ============================================================

    def _run(self) -> None:
        """
        Continuously take jobs from the queue.
        """

        while not self._stop_event.is_set():

            job_id = self.job_queue.get(
                timeout=0.5
            )

            if job_id is None:
                continue

            try:
                result = self.job_processor.process(
                    job_id
                )

                self.last_result = result

                if result.get("success"):
                    self.processed_count += 1
                else:
                    self.failed_count += 1

            except Exception as exc:

                self.last_result = {
                    "success": False,
                    "job_id": job_id,
                    "error": str(exc),
                }

                self.failed_count += 1

            finally:
                self.job_queue.task_done()

    # ============================================================
    # STOP
    # ============================================================

    def stop(
        self,
        timeout: float = 5.0,
    ) -> None:
        """
        Stop the worker gracefully.
        """

        self._stop_event.set()

        if self._thread is not None:

            self._thread.join(
                timeout=timeout
            )

        self._thread = None

    # ============================================================
    # STATUS
    # ============================================================

    def is_running(self) -> bool:
        """
        Return True if worker thread is running.
        """

        return (
            self._thread is not None
            and self._thread.is_alive()
        )

    # ============================================================
    # WAIT
    # ============================================================

    def wait_until_idle(self) -> None:
        """
        Wait until all queued jobs are completed.
        """

        self.job_queue.wait_until_empty()

    # ============================================================
    # STATISTICS
    # ============================================================

    def stats(self) -> dict:

        return {
            "running": self.is_running(),
            "queued_jobs": self.job_queue.size(),
            "processed_count": self.processed_count,
            "failed_count": self.failed_count,
            "last_result": self.last_result,
        }
