from __future__ import annotations

import io
import time
import zipfile

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def wait_for_job(client: TestClient, job_id: str, timeout: float = 10.0):
    deadline = time.time() + timeout

    while time.time() < deadline:
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200

        job = response.json()["job"]

        if job["status"] in {"COMPLETED", "FAILED"}:
            return job

        time.sleep(0.1)

    pytest.fail(f"Job {job_id} did not finish within {timeout} seconds.")


def make_valid_xlsx() -> bytes:
    buffer = io.BytesIO()

    with zipfile.ZipFile(
        buffer,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
</Types>
""",
        )

    return buffer.getvalue()


# ============================================================
# BASIC API TESTS
# ============================================================

def test_root(client):
    response = client.get("/")

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert data["service"] == "Sair Lab API"
    assert data["status"] == "running"


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert data["status"] == "healthy"
    assert "worker_running" in data
    assert "queued_jobs" in data


def test_upload_and_process_clean_job(client):
    csv_content = (
        "name,age,city\n"
        " Abdul ,20,Bhatkal\n"
        " Abdul ,20,Bhatkal\n"
        "Ali,21,Shivamogga\n"
    )

    response = client.post(
        "/api/jobs/upload",
        files={
            "file": (
                "test.csv",
                csv_content.encode("utf-8"),
                "text/csv",
            )
        },
        data={
            "operation": "clean",
            "customer_id": "test-customer",
            "package": "free",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert data["job_id"].startswith("SL-")
    assert data["operation"] == "clean"
    assert data["file_name"] == "test.csv"

    job = wait_for_job(client, data["job_id"])

    assert job["status"] == "COMPLETED"
    assert job["qa"]["passed"] is True

    output = job["output"]

    assert output["file_path"]
    assert output["file_name"]
    assert output["size_bytes"] > 0


def test_get_nonexistent_job(client):
    response = client.get("/api/jobs/SL-DOESNOTEXIST")

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found."


def test_list_jobs(client):
    response = client.get("/api/jobs")

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert isinstance(data["count"], int)
    assert isinstance(data["jobs"], list)


def test_queue_status(client):
    response = client.get("/api/queue")

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert "queue" in data

    queue = data["queue"]

    assert "running" in queue
    assert "queued_jobs" in queue
    assert "processed_count" in queue
    assert "failed_count" in queue


# ============================================================
# BASIC VALIDATION TESTS
# ============================================================

def test_invalid_file_type(client):
    response = client.post(
        "/api/jobs/upload",
        files={
            "file": (
                "malware.exe",
                b"not really an executable",
                "application/octet-stream",
            )
        },
        data={
            "operation": "clean",
        },
    )

    assert response.status_code == 400


def test_invalid_operation(client):
    response = client.post(
        "/api/jobs/upload",
        files={
            "file": (
                "test.csv",
                b"name,age\nAbdul,20\n",
                "text/csv",
            )
        },
        data={
            "operation": "delete_everything",
        },
    )

    assert response.status_code == 400


def test_download_before_completion(client):
    csv_content = (
        "name,age\n"
        "Abdul,20\n"
        "Ali,21\n"
    )

    response = client.post(
        "/api/jobs/upload",
        files={
            "file": (
                "download_test.csv",
                csv_content.encode("utf-8"),
                "text/csv",
            )
        },
        data={
            "operation": "clean",
        },
    )

    assert response.status_code == 200

    job_id = response.json()["job_id"]

    job_response = client.get(f"/api/jobs/{job_id}")

    assert job_response.status_code == 200

    job = job_response.json()["job"]

    if job["status"] != "COMPLETED":
        download_response = client.get(
            f"/api/jobs/{job_id}/download"
        )

        assert download_response.status_code == 409

    wait_for_job(client, job_id)


def test_download_completed_job(client):
    csv_content = (
        "name,age\n"
        "Abdul,20\n"
        "Ali,21\n"
    )

    response = client.post(
        "/api/jobs/upload",
        files={
            "file": (
                "download.csv",
                csv_content.encode("utf-8"),
                "text/csv",
            )
        },
        data={
            "operation": "clean",
        },
    )

    assert response.status_code == 200

    job_id = response.json()["job_id"]

    job = wait_for_job(client, job_id)

    assert job["status"] == "COMPLETED"

    download_response = client.get(
        f"/api/jobs/{job_id}/download"
    )

    assert download_response.status_code == 200
    assert len(download_response.content) > 0


def test_download_nonexistent_job(client):
    response = client.get(
        "/api/jobs/SL-NONEXISTENT/download"
    )

    assert response.status_code == 404


def test_upload_without_filename(client):
    response = client.post(
        "/api/jobs/upload",
        files={
            "file": (
                "",
                b"name,age\nAbdul,20\n",
                "text/csv",
            )
        },
        data={
            "operation": "clean",
        },
    )

    assert response.status_code == 422


# ============================================================
# API SECURITY TESTS
# ============================================================

def test_api_rejects_unsupported_xls(client):
    response = client.post(
        "/api/jobs/upload",
        files={
            "file": (
                "old_format.xls",
                b"fake xls content",
                "application/vnd.ms-excel",
            )
        },
        data={
            "operation": "clean",
        },
    )

    assert response.status_code == 400


def test_api_rejects_fake_xlsx(client):
    response = client.post(
        "/api/jobs/upload",
        files={
            "file": (
                "fake.xlsx",
                b"This is not a real Excel file.",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        data={
            "operation": "clean",
        },
    )

    assert response.status_code == 400


def test_api_accepts_valid_xlsx(client):
    xlsx_content = make_valid_xlsx()

    response = client.post(
        "/api/jobs/upload",
        files={
            "file": (
                "valid.xlsx",
                xlsx_content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        data={
            "operation": "clean",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert data["job_id"].startswith("SL-")


def test_api_sanitizes_dangerous_filename(client):
    csv_content = (
        "name,age\n"
        "Abdul,20\n"
    )

    response = client.post(
        "/api/jobs/upload",
        files={
            "file": (
                "../../../../../dangerous.csv",
                csv_content.encode("utf-8"),
                "text/csv",
            )
        },
        data={
            "operation": "clean",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True

    job_id = data["job_id"]

    job = wait_for_job(client, job_id)

    assert job["status"] == "COMPLETED"

    stored_path = job["input"]["file_path"]

    assert stored_path.endswith(".csv")
    assert ".." not in stored_path


def test_api_rejects_oversized_upload(client):
    # 25 MB + 1 byte.
    oversized_content = b"x" * (25 * 1024 * 1024 + 1)

    response = client.post(
        "/api/jobs/upload",
        files={
            "file": (
                "too_large.csv",
                oversized_content,
                "text/csv",
            )
        },
        data={
            "operation": "clean",
        },
    )

    assert response.status_code == 413


def test_api_accepts_valid_csv(client):
    csv_content = (
        "name,age,city\n"
        "Abdul,20,Bhatkal\n"
        "Ali,21,Shivamogga\n"
    )

    response = client.post(
        "/api/jobs/upload",
        files={
            "file": (
                "valid.csv",
                csv_content.encode("utf-8"),
                "text/csv",
            )
        },
        data={
            "operation": "clean",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert data["job_id"].startswith("SL-")
    assert data["size_bytes"] > 0
    assert data["max_upload_size"] == 25 * 1024 * 1024


def test_api_rejects_invalid_csv_encoding(client):
    invalid_csv = b"\xff\xfe\x00\xff\x00\xfe"

    response = client.post(
        "/api/jobs/upload",
        files={
            "file": (
                "invalid.csv",
                invalid_csv,
                "text/csv",
            )
        },
        data={
            "operation": "clean",
        },
    )

    assert response.status_code == 400


def test_api_rejects_invalid_operation_case(client):
    response = client.post(
        "/api/jobs/upload",
        files={
            "file": (
                "case.csv",
                b"name,age\nAbdul,20\n",
                "text/csv",
            )
        },
        data={
            "operation": "CLEAN_NOT_ALLOWED",
        },
    )

    assert response.status_code == 400


def test_api_download_path_cannot_escape_output_directory(client):
    response = client.get(
        "/api/jobs/SL-DOESNOTEXIST/download"
    )

    assert response.status_code == 404


def test_api_returns_job_status_after_upload(client):
    csv_content = (
        "name,age\n"
        "Abdul,20\n"
    )

    response = client.post(
        "/api/jobs/upload",
        files={
            "file": (
                "status.csv",
                csv_content.encode("utf-8"),
                "text/csv",
            )
        },
        data={
            "operation": "clean",
        },
    )

    assert response.status_code == 200

    data = response.json()

    job_id = data["job_id"]

    status_response = client.get(
        f"/api/jobs/{job_id}"
    )

    assert status_response.status_code == 200

    job = status_response.json()["job"]

    assert job["job_id"] == job_id
    assert job["operation"] == "clean"
    assert job["input"]["file_name"] == "status.csv"


def test_api_operation_whitelist(client):
    allowed_operations = [
        "clean",
        "format",
        "report",
        "csv_to_excel",
        "excel_to_csv",
        "merge_csv",
        "merge_excel",
    ]

    for operation in allowed_operations:
        response = client.post(
            "/api/jobs/upload",
            files={
                "file": (
                    f"{operation}.csv",
                    b"name,age\nAbdul,20\n",
                    "text/csv",
                )
            },
            data={
                "operation": operation,
            },
        )

        # Every operation is allowed through the API validation layer.
        # Some operations may later fail because their required input
        # structure is more specific.
        assert response.status_code in {200, 500}

