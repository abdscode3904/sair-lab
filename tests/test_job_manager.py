from pathlib import Path

from backend.jobs.job_manager import (
    JobManager,
    JobStatus,
)


def test_create_job(tmp_path):

    manager = JobManager(tmp_path)

    job = manager.create_job(
        operation="clean_excel",
        package="basic",
        customer_id="test_customer",
    )

    assert job["job_id"].startswith("SL-")
    assert job["status"] == JobStatus.NEW
    assert job["operation"] == "clean_excel"
    assert job["package"] == "basic"

    saved_job = manager.get_job(
        job["job_id"]
    )

    assert saved_job is not None
    assert saved_job["job_id"] == job["job_id"]


def test_job_status(tmp_path):

    manager = JobManager(tmp_path)

    job = manager.create_job(
        operation="format_excel"
    )

    job_id = job["job_id"]

    manager.set_status(
        job_id,
        JobStatus.PROCESSING,
    )

    updated = manager.get_job(job_id)

    assert updated["status"] == JobStatus.PROCESSING
    assert updated["started_at"] is not None

    manager.complete_job(job_id)

    completed = manager.get_job(job_id)

    assert completed["status"] == JobStatus.COMPLETED
    assert completed["completed_at"] is not None
    assert completed["processing"]["duration_seconds"] is not None


def test_job_qa(tmp_path):

    manager = JobManager(tmp_path)

    job = manager.create_job(
        operation="clean_excel"
    )

    job_id = job["job_id"]

    manager.set_qa_result(
        job_id,
        passed=True,
        errors=[],
        warnings=["Test warning"],
    )

    updated = manager.get_job(job_id)

    assert updated["qa"]["passed"] is True
    assert updated["qa"]["warnings"] == [
        "Test warning"
    ]


def test_failed_job(tmp_path):

    manager = JobManager(tmp_path)

    job = manager.create_job(
        operation="test_failure"
    )

    job_id = job["job_id"]

    manager.fail_job(
        job_id,
        "Test processing error",
    )

    failed = manager.get_job(job_id)

    assert failed["status"] == JobStatus.FAILED
    assert failed["error"] == "Test processing error"
    assert failed["completed_at"] is not None


def test_list_jobs(tmp_path):

    manager = JobManager(tmp_path)

    manager.create_job(
        operation="job_one"
    )

    manager.create_job(
        operation="job_two"
    )

    jobs = manager.list_jobs()

    assert len(jobs) == 2
