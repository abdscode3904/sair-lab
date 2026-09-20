import uuid

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.api.auth import create_access_token, hash_password
from backend.database.database import execute
from backend.services.usage_service import ensure_customer


def create_test_user(customer_id: str):
    ensure_customer(customer_id)

    email = f"{customer_id}@pytest.sairlab.local"
    password_hash = hash_password("TestPassword123!")

    execute(
        """
        INSERT OR IGNORE INTO users
        (customer_id, email, password_hash, plan)
        VALUES (?, ?, ?, 'free')
        """,
        (
            customer_id,
            email,
            password_hash,
        ),
    )

    token = create_access_token(
        customer_id=customer_id,
        email=email,
    )

    return token


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers():
    def _make_headers(customer_id=None):
        if customer_id is None:
            customer_id = f"pytest-{uuid.uuid4().hex}"

        token = create_test_user(customer_id)

        return {
            "Authorization": f"Bearer {token}"
        }

    return _make_headers


@pytest.fixture
def authenticated_client(client, auth_headers):
    customer_id = f"pytest-{uuid.uuid4().hex}"

    client.headers.update(
        auth_headers(customer_id)
    )

    return client


@pytest.fixture(autouse=True)
def automatically_authenticate_legacy_upload_tests(monkeypatch):
    original_post = TestClient.post

    def patched_post(
        self,
        url,
        *args,
        **kwargs,
    ):
        if url == "/api/jobs/upload":
            headers = dict(
                kwargs.get("headers") or {}
            )

            has_authorization = any(
                key.lower() == "authorization"
                for key in headers
            )

            if not has_authorization:
                data = kwargs.get("data") or {}

                requested_customer_id = data.get(
                    "customer_id"
                )

                # Usage tests intentionally use a fixed
                # customer ID because they verify that
                # customer's quota and usage.
                if (
                    requested_customer_id
                    and requested_customer_id.startswith(
                        "usage-test-"
                    )
                ):
                    customer_id = requested_customer_id

                else:
                    # Other legacy tests get an isolated
                    # customer so one test cannot consume
                    # another test's monthly quota.
                    customer_id = (
                        f"pytest-upload-{uuid.uuid4().hex}"
                    )

                token = create_test_user(
                    customer_id
                )

                headers["Authorization"] = (
                    f"Bearer {token}"
                )

                kwargs["headers"] = headers

        return original_post(
            self,
            url,
            *args,
            **kwargs,
        )

    monkeypatch.setattr(
        TestClient,
        "post",
        patched_post,
    )