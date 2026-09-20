from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.database.database import (
    execute,
    fetch_one,
    initialize_database,
)


PLAN_LIMITS: dict[str, dict[str, int | str]] = {
    "free": {
        "monthly_jobs": 10,
        "max_file_size": 25 * 1024 * 1024,
        "ads": 1,
    },
    "pro": {
        "monthly_jobs": 500,
        "max_file_size": 100 * 1024 * 1024,
        "ads": 0,
    },
}


def normalize_plan(plan: str | None) -> str:
    """
    Normalize and validate a plan name.
    """

    normalized = (plan or "free").strip().lower()



    if normalized not in PLAN_LIMITS:
        raise ValueError(
            f"Invalid plan: {plan}"
        )

    return normalized


def get_plan_limits(plan: str | None) -> dict[str, int | str]:
    """
    Return limits for a plan.
    """

    normalized_plan = normalize_plan(plan)

    return dict(PLAN_LIMITS[normalized_plan])


def get_current_month() -> str:
    """
    Return the current UTC month as YYYY-MM.
    """

    return datetime.now(
        timezone.utc
    ).strftime("%Y-%m")


def ensure_customer(
    customer_id: str,
    plan: str = "free",
) -> dict[str, Any]:
    """
    Create a customer if they do not already exist.
    """

    initialize_database()

    customer_id = customer_id.strip()

    if not customer_id:
        raise ValueError(
            "customer_id cannot be empty."
        )

    plan = normalize_plan(plan)

    existing = fetch_one(
        """
        SELECT *
        FROM users
        WHERE customer_id = ?
        """,
        (customer_id,),
    )

    if existing is not None:
        return existing

    execute(
        """
        INSERT INTO users (
            customer_id,
            plan
        )
        VALUES (?, ?)
        """,
        (
            customer_id,
            plan,
        ),
    )

    return fetch_one(
        """
        SELECT *
        FROM users
        WHERE customer_id = ?
        """,
        (customer_id,),
    )


def get_customer(
    customer_id: str,
) -> dict[str, Any] | None:
    """
    Return customer information.
    """

    initialize_database()

    return fetch_one(
        """
        SELECT *
        FROM users
        WHERE customer_id = ?
        """,
        (customer_id,),
    )


def get_customer_plan(
    customer_id: str,
) -> str:
    """
    Return the customer's current plan.
    """

    customer = get_customer(customer_id)

    if customer is None:
        return "free"

    return normalize_plan(
        customer.get("plan")
    )


def get_usage(
    customer_id: str,
    usage_month: str | None = None,
) -> dict[str, Any]:
    """
    Return monthly usage for a customer.
    """

    initialize_database()

    month = usage_month or get_current_month()

    existing = fetch_one(
        """
        SELECT
            customer_id,
            usage_month,
            jobs_count,
            total_bytes
        FROM usage
        WHERE customer_id = ?
        AND usage_month = ?
        """,
        (
            customer_id,
            month,
        ),
    )

    if existing is not None:
        return existing

    execute(
        """
        INSERT OR IGNORE INTO usage (
            customer_id,
            usage_month,
            jobs_count,
            total_bytes
        )
        VALUES (?, ?, 0, 0)
        """,
        (
            customer_id,
            month,
        ),
    )

    return fetch_one(
        """
        SELECT
            customer_id,
            usage_month,
            jobs_count,
            total_bytes
        FROM usage
        WHERE customer_id = ?
        AND usage_month = ?
        """,
        (
            customer_id,
            month,
        ),
    )


def get_remaining_jobs(
    customer_id: str,
) -> int:
    """
    Return the number of jobs remaining this month.
    """

    customer = ensure_customer(customer_id)

    plan = normalize_plan(
        customer["plan"]
    )

    limits = get_plan_limits(plan)

    usage = get_usage(customer_id)

    monthly_limit = int(
        limits["monthly_jobs"]
    )

    jobs_used = int(
        usage["jobs_count"]
    )

    return max(
        0,
        monthly_limit - jobs_used,
    )


def can_create_job(
    customer_id: str,
    file_size: int,
) -> tuple[bool, str]:
    """
    Check whether a customer can create a new job.
    """

    if file_size < 0:
        return False, "Invalid file size."

    customer = ensure_customer(
        customer_id
    )

    plan = normalize_plan(
        customer["plan"]
    )

    limits = get_plan_limits(plan)

    max_file_size = int(
        limits["max_file_size"]
    )

    if file_size > max_file_size:
        max_mb = max_file_size / (
            1024 * 1024
        )

        return (
            False,
            f"File is too large for the {plan} plan. "
            f"Maximum allowed size is {max_mb:g} MB.",
        )

    remaining = get_remaining_jobs(
        customer_id
    )

    if remaining <= 0:
        monthly_jobs = int(
            limits["monthly_jobs"]
        )

        return (
            False,
            f"Monthly job limit reached. "
            f"The {plan} plan allows "
            f"{monthly_jobs} jobs per month.",
        )

    return True, "Usage allowed."


def record_job_usage(
    customer_id: str,
    file_size: int,
) -> dict[str, Any]:
    """
    Record one successfully accepted job.
    """

    if file_size < 0:
        raise ValueError(
            "Invalid file size."
        )

    initialize_database()

    month = get_current_month()

    get_usage(
        customer_id,
        month,
    )

    execute(
        """
        UPDATE usage
        SET
            jobs_count = jobs_count + 1,
            total_bytes = total_bytes + ?
        WHERE customer_id = ?
        AND usage_month = ?
        """,
        (
            file_size,
            customer_id,
            month,
        ),
    )

    return get_usage(
        customer_id,
        month,
    )


def set_customer_plan(
    customer_id: str,
    plan: str,
) -> dict[str, Any]:
    """
    Change a customer's plan.
    """

    initialize_database()

    plan = normalize_plan(plan)

    customer = ensure_customer(
        customer_id,
        plan="free",
    )

    execute(
        """
        UPDATE users
        SET plan = ?
        WHERE customer_id = ?
        """,
        (
            plan,
            customer_id,
        ),
    )

    return get_customer(
        customer["customer_id"]
    )


def get_usage_summary(
    customer_id: str,
) -> dict[str, Any]:
    """
    Return plan, limits, usage and remaining quota.
    """

    customer = ensure_customer(
        customer_id
    )

    plan = normalize_plan(
        customer["plan"]
    )

    limits = get_plan_limits(plan)

    usage = get_usage(
        customer_id
    )

    monthly_jobs = int(
        limits["monthly_jobs"]
    )

    jobs_used = int(
        usage["jobs_count"]
    )

    return {
        "customer_id": customer_id,
        "plan": plan,
        "usage_month": usage["usage_month"],
        "jobs_used": jobs_used,
        "jobs_remaining": max(
            0,
            monthly_jobs - jobs_used,
        ),
        "monthly_job_limit": monthly_jobs,
        "total_bytes": int(
            usage["total_bytes"]
        ),
        "max_file_size": int(
            limits["max_file_size"]
        ),
        "ads": bool(
            int(limits["ads"])
        ),
    }

