import pytest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.api.main import app
from backend.database.database import execute
from backend.services.usage_service import (
    ensure_customer,
    get_usage_summary,
    record_job_usage,
    set_customer_plan,
)


TEST_FILE = Path("storage/uploads/customer_sales.xlsx")


# =========================================================
# TEST DATABASE CLEANUP
# =========================================================

TEST_CUSTOMERS = [
    "usage-test-consume",
    "usage-test-limit",
    "usage-test-file-limit",
    "usage-test-package-security",
    "usage-test-pro",
    "usage-test-summary",
    "usage-test-server-plan",
]


@pytest.fixture(autouse=True)
def clean_test_customers():
    """
    Remove persistent database state before and after
    every usage test.

    Production usage data is NOT affected.
    """

    for customer_id in TEST_CUSTOMERS:
        execute(
            "DELETE FROM usage WHERE customer_id = ?",
            (customer_id,),
        )

        execute(
            "DELETE FROM users WHERE customer_id = ?",
            (customer_id,),
        )

        execute(
            "DELETE FROM jobs WHERE customer_id = ?",
            (customer_id,),
        )

    yield

    for customer_id in TEST_CUSTOMERS:
        execute(
            "DELETE FROM usage WHERE customer_id = ?",
            (customer_id,),
        )

        execute(
            "DELETE FROM users WHERE customer_id = ?",
            (customer_id,),
        )

        execute(
            "DELETE FROM jobs WHERE customer_id = ?",
            (customer_id,),
        )


# =========================================================
# TEST 1
# =========================================================

def test_customer_upload_consumes_usage():
    customer_id = "usage-test-consume"

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


# =========================================================
# TEST 2
# =========================================================

def test_free_customer_11th_job_is_rejected():
    customer_id = "usage-test-limit"

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


# =========================================================
# TEST 3
# =========================================================

def test_free_customer_file_size_limit():
    customer_id = "usage-test-file-limit"

    ensure_customer(customer_id)

    # 25 MB + 1 byte
    oversized_file = b"0" * (
        25 * 1024 * 1024 + 1
    )

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


# =========================================================
# TEST 4
# =========================================================

def test_client_cannot_upgrade_customer_with_package_field():
    customer_id = "usage-test-package-security"

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


# =========================================================
# TEST 5
# =========================================================

def test_pro_customer_has_500_job_limit():
    customer_id = "usage-test-pro"

    ensure_customer(customer_id)

    set_customer_plan(
        customer_id,
        "pro",
    )

    usage = get_usage_summary(customer_id)

    assert usage["plan"] == "pro"
    assert usage["monthly_job_limit"] == 500
    assert usage["jobs_remaining"] == 500


# =========================================================
# TEST 6
# =========================================================

def test_usage_summary_after_multiple_jobs():
    customer_id = "usage-test-summary"

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


# =========================================================
# TEST 7
# =========================================================

def test_customer_plan_is_server_side():
    customer_id = "usage-test-server-plan"

    ensure_customer(customer_id)

    set_customer_plan(
        customer_id,
        "pro",
    )

    usage = get_usage_summary(customer_id)

    assert usage["plan"] == "pro"
    assert usage["monthly_job_limit"] == 500