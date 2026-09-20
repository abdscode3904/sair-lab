from pathlib import Path

from fastapi.testclient import TestClient

from backend.api.main import app
from backend.database.database import initialize_database
from backend.services.usage_service import (
    ensure_customer,
    get_usage_summary,
    record_job_usage,
    set_customer_plan,
)


TEST_FILE = Path("storage/uploads/customer_sales.xlsx")


def test_customer_upload_consumes_usage():
    customer_id = "test-customer"
    ensure_customer(customer_id)

    with TestClient(app) as client:
        with open(TEST_FILE, "rb") as file:
            response = client.post(
                "/api/jobs/upload",
                files={
                    "file": (
                        "customer_sales.xlsx",
                        file,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                },
                data={
                    "operation": "clean",
                    "customer_id": customer_id,
                },
            )

    assert response.status_code == 200

    usage = get_usage_summary(customer_id)

    assert usage["jobs_used"] == 1
    assert usage["jobs_remaining"] == 9


def test_free_customer_11th_job_is_rejected():
    customer_id = "test-customer"

    ensure_customer(customer_id)

    for _ in range(10):
        record_job_usage(
            customer_id,
            100,
        )

    usage = get_usage_summary(customer_id)

    assert usage["jobs_used"] == 10
    assert usage["jobs_remaining"] == 0

    with TestClient(app) as client:
        with open(TEST_FILE, "rb") as file:
            response = client.post(
                "/api/jobs/upload",
                files={
                    "file": (
                        "customer_sales.xlsx",
                        file,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                },
                data={
                    "operation": "clean",
                    "customer_id": customer_id,
                },
            )

    assert response.status_code == 429


def test_free_customer_file_size_limit():
    customer_id = "usage-test-file-limit"

    ensure_customer(customer_id)

    # 25 MB + 1 byte
    oversized_file = b"0" * (25 * 1024 * 1024 + 1)

    with TestClient(app) as client:
        response = client.post(
            "/api/jobs/upload",
            files={
                "file": (
                    "large.csv",
                    oversized_file,
                    "text/csv",
                )
            },
            data={
                "operation": "clean",
                "customer_id": customer_id,
            },
        )

    assert response.status_code == 413


def test_client_cannot_upgrade_customer_with_package_field():
    customer_id = "test-customer"

    ensure_customer(customer_id)

    with TestClient(app) as client:
        with open(TEST_FILE, "rb") as file:
            response = client.post(
                "/api/jobs/upload",
                files={
                    "file": (
                        "customer_sales.xlsx",
                        file,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                },
                data={
                    "operation": "clean",
                    "customer_id": customer_id,
                    "package": "pro",
                },
            )

    assert response.status_code == 200

    usage = get_usage_summary(customer_id)

    assert usage["plan"] == "free"


def test_pro_customer_has_500_job_limit():
    customer_id = "test-customer"

    ensure_customer(customer_id)
    set_customer_plan(
        customer_id,
        "pro",
    )

    usage = get_usage_summary(customer_id)

    assert usage["plan"] == "pro"
    assert usage["monthly_job_limit"] == 500
    assert usage["jobs_remaining"] == 500


def test_usage_summary_after_multiple_jobs():
    customer_id = "test-customer"

    ensure_customer(customer_id)

    record_job_usage(
        customer_id,
        1000,
    )

    record_job_usage(
        customer_id,
        2000,
    )

    usage = get_usage_summary(customer_id)

    assert usage["jobs_used"] == 2
    assert usage["jobs_remaining"] == 8
    assert usage["total_bytes"] == 3000


def test_customer_plan_is_server_side():
    customer_id = "test-customer"

    ensure_customer(customer_id)

    set_customer_plan(
        customer_id,
        "pro",
    )

    usage = get_usage_summary(customer_id)

    assert usage["plan"] == "pro"
    assert usage["monthly_job_limit"] == 500
