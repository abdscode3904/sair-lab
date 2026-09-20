from __future__ import annotations

import json
import os
import shutil
import threading
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class JobStatus(str, Enum):
    NEW = "NEW"
    PROCESSING = "PROCESSING"
    QA = "QA"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class JobManager:
    """
    Sair Lab Job Manager

    Responsible for:
    - Creating jobs
    - Storing job metadata
    - Tracking job status
    - Tracking input/output files
    - Tracking processing statistics
    - Tracking QA results
    - Recording errors
    - Persisting job data as JSON

    Storage structure:

        storage/
        └── jobs/
            └── SL-XXXXXXXXXXXX/
                └── job.json
    """

    def __init__(
        self,
        jobs_directory: Optional[str | Path] = None,
    ):
        if jobs_directory is None:
            project_root = Path(__file__).resolve().parents[2]
            jobs_directory = (
                project_root
                / "storage"
                / "jobs"
            )

        self.jobs_directory = Path(
            jobs_directory
        ).resolve()

        self.jobs_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        # Protects concurrent API/worker access to job JSON files.
        self._lock = threading.RLock()

    # ============================================================
    # INTERNAL HELPERS
    # ============================================================

    @staticmethod
    def _timestamp() -> str:
        """
        Return current UTC timestamp in ISO format.
        """
        return datetime.now(
            timezone.utc
        ).isoformat()

    @staticmethod
    def _generate_job_id() -> str:
        """
        Generate unique Sair Lab job ID.

        Example:
            SL-8F3A12B91C42
        """
        return (
            "SL-"
            + uuid.uuid4().hex[:12].upper()
        )

    def _job_directory(
        self,
        job_id: str,
    ) -> Path:
        return (
            self.jobs_directory
            / job_id
        )

    def _job_file(
        self,
        job_id: str,
    ) -> Path:
        return (
            self._job_directory(job_id)
            / "job.json"
        )

    def _save_job(
        self,
        job: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Atomically persist a job.

        The old implementation wrote directly to job.json.
        That allowed another thread to observe a partially
        written JSON file.

        We now:
        1. Write the complete JSON to a temporary file.
        2. Flush and fsync it.
        3. Atomically replace job.json.

        This means readers see either the old complete file
        or the new complete file, never a half-written file.
        """

        job_id = job["job_id"]

        directory = self._job_directory(
            job_id
        )

        directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        job_file = self._job_file(
            job_id
        )

        temp_file = directory / (
            f".job-{uuid.uuid4().hex}.tmp"
        )

        with self._lock:
            try:
                with open(
                    temp_file,
                    "w",
                    encoding="utf-8",
                ) as file:
                    json.dump(
                        job,
                        file,
                        indent=2,
                        ensure_ascii=False,
                    )

                    file.flush()
                    os.fsync(file.fileno())

                # Atomic replacement on the same filesystem.
                os.replace(
                    temp_file,
                    job_file,
                )

            finally:
                # Cleanup if anything failed before os.replace().
                try:
                    if temp_file.exists():
                        temp_file.unlink()
                except OSError:
                    pass

        return job

    def _load_job(
        self,
        job_id: str,
    ) -> Optional[dict[str, Any]]:
        """
        Load a job safely.

        Because _save_job() uses atomic replacement,
        this should never observe a partially written JSON file.
        """

        job_file = self._job_file(
            job_id
        )

        with self._lock:
            if not job_file.exists():
                return None

            try:
                with open(
                    job_file,
                    "r",
                    encoding="utf-8",
                ) as file:
                    return json.load(file)

            except (
                json.JSONDecodeError,
                OSError,
            ):
                return None

    # ============================================================
    # CREATE JOB
    # ============================================================

    def create_job(
        self,
        customer_id: Optional[str] = None,
        package: Optional[str] = None,
        operation: Optional[str] = None,
    ) -> dict[str, Any]:

        job_id = self._generate_job_id()
        now = self._timestamp()

        job: dict[str, Any] = {
            "job_id": job_id,

            "status": JobStatus.NEW.value,

            "created_at": now,
            "started_at": None,
            "completed_at": None,

            "customer_id": customer_id,
            "package": package,
            "operation": operation,

            "input": {
                "file_name": None,
                "file_path": None,
                "size_bytes": None,
            },

            "output": {
                "file_name": None,
                "file_path": None,
                "size_bytes": None,
                "rows": None,
                "columns": None,
            },

            "processing": {
                "duration_seconds": None,
                "rows_before": None,
                "rows_after": None,
                "columns_before": None,
                "columns_after": None,
            },

            "qa": {
                "passed": None,
                "errors": [],
                "warnings": [],
            },

            "error": None,
        }

        return self._save_job(job)

    # ============================================================
    # GET JOB
    # ============================================================

    def get_job(
        self,
        job_id: str,
    ) -> Optional[dict[str, Any]]:

        return self._load_job(job_id)

    # ============================================================
    # UPDATE JOB
    # ============================================================

    def update_job(
        self,
        job_id: str,
        updates: dict[str, Any],
    ) -> Optional[dict[str, Any]]:

        with self._lock:
            job = self._load_job(job_id)

            if job is None:
                return None

            job.update(updates)

            return self._save_job(job)

    # ============================================================
    # STATUS
    # ============================================================

    def set_status(
        self,
        job_id: str,
        status: JobStatus | str,
    ) -> Optional[dict[str, Any]]:

        with self._lock:
            job = self._load_job(job_id)

            if job is None:
                return None

            if isinstance(status, JobStatus):
                status_value = status.value
            else:
                status_value = str(status)

            job["status"] = status_value

            if status_value == JobStatus.PROCESSING.value:
                if job.get("started_at") is None:
                    job["started_at"] = self._timestamp()

            return self._save_job(job)

    # ============================================================
    # INPUT STATS
    # ============================================================

    def set_input_stats(
        self,
        job_id: str,
        rows: int | None = None,
        columns: int | None = None,
    ) -> Optional[dict[str, Any]]:

        with self._lock:
            job = self._load_job(job_id)

            if job is None:
                return None

            processing = job.setdefault(
                "processing",
                {},
            )

            processing["rows_before"] = rows
            processing["columns_before"] = columns

            return self._save_job(job)

    # ============================================================
    # OUTPUT
    # ============================================================

    def set_output(
        self,
        job_id: str,
        output_file: str | Path,
        rows: int | None = None,
        columns: int | None = None,
    ) -> Optional[dict[str, Any]]:

        with self._lock:
            job = self._load_job(job_id)

            if job is None:
                return None

            output_path = Path(
                output_file
            ).resolve()

            output_size: int | None = None

            if output_path.exists():
                output_size = output_path.stat().st_size

            output = job.setdefault(
                "output",
                {},
            )

            output["file_name"] = (
                output_path.name
            )

            output["file_path"] = (
                str(output_path)
            )

            output["size_bytes"] = (
                output_size
            )

            output["rows"] = rows
            output["columns"] = columns

            processing = job.setdefault(
                "processing",
                {},
            )

            processing["rows_after"] = rows
            processing["columns_after"] = columns

            return self._save_job(job)

    # ============================================================
    # QA
    # ============================================================

    def set_qa_result(
        self,
        job_id: str,
        passed: bool,
        errors: list[str] | None = None,
        warnings: list[str] | None = None,
    ) -> Optional[dict[str, Any]]:

        with self._lock:
            job = self._load_job(job_id)

            if job is None:
                return None

            job["qa"] = {
                "passed": bool(passed),
                "errors": list(errors or []),
                "warnings": list(warnings or []),
            }

            return self._save_job(job)

    # ============================================================
    # COMPLETE JOB
    # ============================================================

    def complete_job(
        self,
        job_id: str,
    ) -> Optional[dict[str, Any]]:

        with self._lock:
            job = self._load_job(job_id)

            if job is None:
                return None

            job["status"] = (
                JobStatus.COMPLETED.value
            )

            job["completed_at"] = (
                self._timestamp()
            )

            self._calculate_duration(job)

            job["error"] = None

            return self._save_job(job)

    # ============================================================
    # FAIL JOB
    # ============================================================

    def fail_job(
        self,
        job_id: str,
        error: str,
    ) -> Optional[dict[str, Any]]:

        with self._lock:
            job = self._load_job(job_id)

            if job is None:
                return None

            job["status"] = (
                JobStatus.FAILED.value
            )

            job["completed_at"] = (
                self._timestamp()
            )

            job["error"] = str(error)

            self._calculate_duration(job)

            return self._save_job(job)

    # ============================================================
    # DURATION
    # ============================================================

    def _calculate_duration(
        self,
        job: dict[str, Any],
    ) -> None:

        started_at = job.get(
            "started_at"
        )

        completed_at = job.get(
            "completed_at"
        )

        if not started_at or not completed_at:
            return

        try:
            started = datetime.fromisoformat(
                started_at
            )

            completed = datetime.fromisoformat(
                completed_at
            )

            duration = (
                completed - started
            ).total_seconds()

            job.setdefault(
                "processing",
                {},
            )[
                "duration_seconds"
            ] = round(
                max(duration, 0),
                3,
            )

        except (
            ValueError,
            TypeError,
        ):
            pass

    # ============================================================
    # LIST JOBS
    # ============================================================

    def list_jobs(
        self,
        status: JobStatus | str | None = None,
        customer_id: str | None = None,
    ) -> list[dict[str, Any]]:

        jobs: list[dict[str, Any]] = []

        with self._lock:
            if not self.jobs_directory.exists():
                return jobs

            for job_file in self.jobs_directory.glob(
                "*/job.json"
            ):
                try:
                    with open(
                        job_file,
                        "r",
                        encoding="utf-8",
                    ) as file:
                        job = json.load(file)

                except (
                    json.JSONDecodeError,
                    OSError,
                ):
                    continue

                if status is not None:

                    status_value = (
                        status.value
                        if isinstance(
                            status,
                            JobStatus,
                        )
                        else str(status)
                    )

                    if job.get("status") != status_value:
                        continue

                if customer_id is not None:

                    if (
                        job.get("customer_id")
                        != customer_id
                    ):
                        continue

                jobs.append(job)

            jobs.sort(
                key=lambda item: item.get(
                    "created_at",
                    "",
                ),
                reverse=True,
            )

        return jobs

    # ============================================================
    # DELETE JOB
    # ============================================================

    def delete_job(
        self,
        job_id: str,
    ) -> bool:

        job_directory = self._job_directory(
            job_id
        )

        with self._lock:
            if not job_directory.exists():
                return False

            try:
                shutil.rmtree(
                    job_directory
                )

                return True

            except OSError:
                return False

    # ============================================================
    # JOB COUNTS
    # ============================================================

    def count_jobs(
        self,
        status: JobStatus | str | None = None,
    ) -> int:

        return len(
            self.list_jobs(
                status=status
            )
        )

    # ============================================================
    # EXISTENCE CHECK
    # ============================================================

    def job_exists(
        self,
        job_id: str,
    ) -> bool:

        with self._lock:
            return self._job_file(
                job_id
            ).exists()
