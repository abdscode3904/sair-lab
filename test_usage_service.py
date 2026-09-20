from __future__ import annotations

import backend.database.database as database_module

from backend.services.usage_service import (
    PLAN_LIMITS,
    can_create_job,
    ensure_customer,
    get_plan_limits,
    get_remaining_jobs,
    get_usage,
    get_usage_summary,
    record_job_usage,
    set_customer_plan,
)


def test_free_plan_limits():
    limits = get_plan_limits("free")

    assert limits["monthly_jobs"] == 10
    assert limits["max_file_size"] == 25 * 1024 * 1024
    assert limits["ads"] == 1


def test_pro_plan_limits():
    limits = get_plan_limits("pro")

    assert limits["monthly_jobs"] == 500
    assert limits["max_file_size"] == 100 * 1024 * 1024
    assert limits["ads"] == 0


def test_invalid_plan():
    try:
        get_plan_limits("enterprise")
        assert False
    except ValueError:
        assert True


def test_create_customer(tmp_path, monkeypatch):
    database_path = tmp_path / "test.db"

    monkeypatch.setattr(
        database_module,
        "DATABASE_PATH",
        database_path,
    )

    customer = ensure_customer(
        "customer-001",
        "free",
    )

    assert customer["customer_id"] == "customer-001"
    assert customer["plan"] == "free"


def test_customer_is_not_duplicated(tmp_path, monkeypatch):
    database_path = tmp_path / "test.db"

    monkeypatch.setattr(
        database_module,
        "DATABASE_PATH",
        database_path,
    )

    first = ensure_customer(
        "customer-002",
        "free",
    )

    second = ensure_customer(
        "customer-002",
        "free",
    )

    assert first["customer_id"] == second["customer_id"]


def test_initial_usage_is_zero(tmp_path, monkeypatch):
    database_path = tmp_path / "test.db"

    monkeypatch.setattr(
        database_module,
        "DATABASE_PATH",
        database_path,
    )

    ensure_customer(
        "customer-003"
    )

    usage = get_usage(
        "customer-003"
    )

    assert usage["jobs_count"] == 0
    assert usage["total_bytes"] == 0


def test_free_customer_can_create_job(tmp_path, monkeypatch):
    database_path = tmp_path / "test.db"

    monkeypatch.setattr(
        database_module,
        "DATABASE_PATH",
        database_path,
    )

    allowed, message = can_create_job(
        "customer-004",
        1024,
    )

    assert allowed is True
    assert message == "Usage allowed."


def test_file_size_limit(tmp_path, monkeypatch):
    database_path = tmp_path / "test.db"

    monkeypatch.setattr(
        database_module,
        "DATABASE_PATH",
        database_path,
    )

    allowed, message = can_create_job(
        "customer-005",
        26 * 1024 * 1024,
    )

    assert allowed is False
    assert "too large" in message


def test_record_usage(tmp_path, monkeypatch):
    database_path = tmp_path / "test.db"

    monkeypatch.setattr(
        database_module,
        "DATABASE_PATH",
        database_path,
    )

    ensure_customer(
        "customer-006"
    )

    usage = record_job_usage(
        "customer-006",
        5000,
    )

    assert usage["jobs_count"] == 1
    assert usage["total_bytes"] == 5000


def test_remaining_jobs_decreases(tmp_path, monkeypatch):
    database_path = tmp_path / "test.db"

    monkeypatch.setattr(
        database_module,
        "DATABASE_PATH",
        database_path,
    )

    customer_id = "customer-007"

    ensure_customer(
        customer_id
    )

    assert get_remaining_jobs(
        customer_id
    ) == 10

    record_job_usage(
        customer_id,
        1000,
    )

    assert get_remaining_jobs(
        customer_id
    ) == 9


def test_free_monthly_limit(tmp_path, monkeypatch):
    database_path = tmp_path / "test.db"

    monkeypatch.setattr(
        database_module,
        "DATABASE_PATH",
        database_path,
    )

    customer_id = "customer-008"

    ensure_customer(
        customer_id
    )

    for _ in range(10):
        record_job_usage(
            customer_id,
            100,
        )

    allowed, message = can_create_job(
        customer_id,
        100,
    )

    assert allowed is False
    assert "Monthly job limit reached" in message


def test_pro_plan_has_higher_limit(tmp_path, monkeypatch):
    database_path = tmp_path / "test.db"

    monkeypatch.setattr(
        database_module,
        "DATABASE_PATH",
        database_path,
    )

    customer_id = "customer-009"

    ensure_customer(
        customer_id
    )

    set_customer_plan(
        customer_id,
        "pro",
    )

    allowed, message = can_create_job(
        customer_id,
        50 * 1024 * 1024,
    )

    assert allowed is True
    assert message == "Usage allowed."


def test_usage_summary(tmp_path, monkeypatch):
    database_path = tmp_path / "test.db"

    monkeypatch.setattr(
        database_module,
        "DATABASE_PATH",
        database_path,
    )

    customer_id = "customer-010"

    ensure_customer(
        customer_id
    )

    record_job_usage(
        customer_id,
        2048,
    )

    summary = get_usage_summary(
        customer_id
    )

    assert summary["customer_id"] == customer_id
    assert summary["plan"] == "free"
    assert summary["jobs_used"] == 1
    assert summary["jobs_remaining"] == 9
    assert summary["total_bytes"] == 2048


def test_plan_limits_are_defined():
    assert "free" in PLAN_LIMITS
    assert "pro" in PLAN_LIMITS

