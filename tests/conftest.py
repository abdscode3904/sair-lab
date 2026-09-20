from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.api.auth import get_current_user
from backend.database.database import execute
from backend.services.usage_service import ensure_customer


TEST_CUSTOMER_ID = "test-customer"
TEST_EMAIL = "test@sairlab.local"


def test_current_user():
    """
    Fake authenticated user used only during pytest.
    Production authentication is unchanged.
    """
    return {
        "customer_id": TEST_CUSTOMER_ID,
        "email": TEST_EMAIL,
        "plan": "free",
    }


@pytest.fixture(autouse=True)
def reset_test_customer():
    """
    Give every test using the shared test customer a clean
    monthly usage counter.

    This prevents one test's uploads from consuming the quota
    of another test.

    Production database and production usage behavior are unchanged.
    """

    # Make sure the test customer exists.
    ensure_customer(
        TEST_CUSTOMER_ID,
        plan="free",
    )

    # Always start this test with zero monthly usage.
    execute(
        """
        DELETE FROM usage
        WHERE customer_id = ?
        """,
        (
            TEST_CUSTOMER_ID,
        ),
    )

    # Make sure the test customer is on the free plan.
    execute(
        """
        UPDATE users
        SET plan = 'free'
        WHERE customer_id = ?
        """,
        (
            TEST_CUSTOMER_ID,
        ),
    )

    # Authenticate all API dependencies during pytest.
    app.dependency_overrides[get_current_user] = test_current_user

    yield

    # Remove the authentication override after the test.
    app.dependency_overrides.pop(
        get_current_user,
        None,
    )


@pytest.fixture
def client():
    """
    Shared authenticated TestClient.
    """
    with TestClient(app) as test_client:
        yield test_client