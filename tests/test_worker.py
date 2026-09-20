from pathlib import Path
import time

import pandas as pd

from backend.jobs.job_manager import JobManager, JobStatus
from backend.jobs.job_processor import JobProcessor
from backend.jobs.job_queue import JobQueue
from backend.jobs.worker import JobWorker


def create_input(path: Path):

    df = pd.DataFrame(
        {
            "Name": [
                " Abdul ",
                "Ali",
                " Abdul ",
            ],
            "Sales": [
                100,
                200,
                100,
            ],
        }
    )

    df.to_excel(
        path,
        index=False,
    )


def test_worker_processes_job(tmp_path):

    storage = tmp_path / "storage"

    uploads = storage / "uploads"
    uploads.mkdir(
        parents=True
    )

    input_file = (
        uploads / "input.xlsx"
    )

    create_input(input_file)

    manager = JobManager(
        jobs_directory=storage / "jobs"
    )

    job = manager.create_job(
        customer_id="test-user",
        package="basic",
        operation="clean",
    )

    processor = JobProcessor(
        job_manager=manager,
        project_root=tmp_path,
    )

    queue = JobQueue()

    worker = JobWorker(
        job_queue=queue,
        job_processor=processor,
    )

    # The processor normally receives the input path
    # directly. For the worker test, store it in the job.
    manager.update_job(
        job["job_id"],
        {
            "input": {
                "file_name": input_file.name,
                "file_path": str(input_file),
                "size_bytes": input_file.stat().st_size,
            }
        },
    )

    worker.start()

    assert worker.is_running() is True

    assert queue.add(
        job["job_id"]
    ) is True

    worker.wait_until_idle()

    # Give the worker thread a moment to finish
    # updating the job.
    for _ in range(20):

        updated = manager.get_job(
            job["job_id"]
        )

        if updated["status"] in {
            JobStatus.COMPLETED.value,
            JobStatus.FAILED.value,
        }:
            break

        time.sleep(0.05)

    worker.stop()

    updated = manager.get_job(
        job["job_id"]
    )

    assert updated["status"] == (
        JobStatus.COMPLETED.value
    )

    assert worker.processed_count == 1

    output_path = Path(
        updated["output"]["file_path"]
    )

    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_worker_starts_and_stops(tmp_path):

    manager = JobManager(
        jobs_directory=tmp_path / "jobs"
    )

    processor = JobProcessor(
        job_manager=manager,
        project_root=tmp_path,
    )

    queue = JobQueue()

    worker = JobWorker(
        job_queue=queue,
        job_processor=processor,
    )

    assert worker.is_running() is False

    worker.start()

    assert worker.is_running() is True

    worker.stop()

    assert worker.is_running() is False


def test_worker_stats(tmp_path):

    manager = JobManager(
        jobs_directory=tmp_path / "jobs"
    )

    processor = JobProcessor(
        job_manager=manager,
        project_root=tmp_path,
    )

    queue = JobQueue()

    worker = JobWorker(
        job_queue=queue,
        job_processor=processor,
    )

    stats = worker.stats()

    assert stats["running"] is False
    assert stats["queued_jobs"] == 0
    assert stats["processed_count"] == 0
    assert stats["failed_count"] == 0