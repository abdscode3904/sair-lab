from pathlib import Path

import pandas as pd

from backend.jobs.job_manager import JobManager, JobStatus
from backend.jobs.job_processor import JobProcessor


def create_test_input(path: Path):
    df = pd.DataFrame({
        "Name": [" Abdul ", "Ali", " Abdul "],
        "Sales": [100, 200, 100],
    })

    df.to_excel(path, index=False)


def test_clean_job(tmp_path):
    storage = tmp_path / "storage"
    uploads = storage / "uploads"

    uploads.mkdir(parents=True)

    input_file = uploads / "input.xlsx"

    create_test_input(input_file)

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

    result = processor.process(
        job_id=job["job_id"],
        input_path=input_file,
        operation="clean",
    )

    assert result["success"] is True
    assert result["status"] == JobStatus.COMPLETED

    output_path = Path(result["output_path"])

    assert output_path.exists()
    assert output_path.stat().st_size > 0

    updated_job = manager.get_job(
        job["job_id"]
    )

    assert updated_job["status"] == JobStatus.COMPLETED


def test_failed_job(tmp_path):
    storage = tmp_path / "storage"

    manager = JobManager(
        jobs_directory=storage / "jobs"
    )

    job = manager.create_job(
        customer_id="test-user",
        package="basic",
        operation="invalid_operation",
    )

    processor = JobProcessor(
        job_manager=manager,
        project_root=tmp_path,
    )

    result = processor.process(
        job_id=job["job_id"],
        input_path=tmp_path / "missing.xlsx",
        operation="invalid_operation",
    )

    assert result["success"] is False

    updated_job = manager.get_job(
        job["job_id"]
    )

    assert updated_job["status"] == JobStatus.FAILED