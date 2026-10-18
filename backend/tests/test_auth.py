"""API-level tests for authentication, logout, and business isolation."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    """Run API requests against an isolated in-memory database."""
    monkeypatch.setenv("AUTH_SECRET_KEY", "test-only-secret-value-with-more-than-32-bytes")
    get_settings.cache_clear()
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)

    def override_get_db() -> Generator[Session, None, None]:
        with test_session() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    app.state.test_session = test_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    del app.state.test_session
    engine.dispose()
    get_settings.cache_clear()


def register(
    client: TestClient,
    email: str,
    business_name: str = "Market Stall",
) -> dict:
    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "correct-horse-battery-7",
            "business_name": business_name,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_registration_creates_owner_business_and_private_identity(
    client: TestClient,
) -> None:
    result = register(client, "Owner@Example.com", "My Shop")
    token = result["access_token"]

    identity = client.get("/auth/me", headers=bearer(token))
    assert identity.status_code == 200
    assert identity.json()["email"] == "owner@example.com"
    assert "password_hash" not in identity.json()

    businesses = client.get("/businesses", headers=bearer(token))
    assert businesses.status_code == 200
    assert len(businesses.json()) == 1
    assert businesses.json()[0]["name"] == "My Shop"
    assert businesses.json()[0]["currency_code"] == "NGN"


def test_login_rejects_wrong_password_and_logout_revokes_token(
    client: TestClient,
) -> None:
    register(client, "owner@example.com")
    wrong = client.post(
        "/auth/login",
        json={"email": "owner@example.com", "password": "not-the-password"},
    )
    assert wrong.status_code == 401

    login = client.post(
        "/auth/login",
        json={"email": "OWNER@example.com", "password": "correct-horse-battery-7"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    assert client.get("/auth/me", headers=bearer(token)).status_code == 200

    logout = client.post("/auth/logout", headers=bearer(token))
    assert logout.status_code == 204
    assert client.get("/auth/me", headers=bearer(token)).status_code == 401


def test_duplicate_email_is_rejected(client: TestClient) -> None:
    register(client, "owner@example.com")
    duplicate = client.post(
        "/auth/register",
        json={
            "email": "OWNER@example.com",
            "password": "correct-horse-battery-7",
            "business_name": "Another Shop",
        },
    )
    assert duplicate.status_code == 409


def test_user_cannot_access_another_users_business(client: TestClient) -> None:
    first = register(client, "first@example.com", "First Shop")
    second = register(client, "second@example.com", "Second Shop")
    second_businesses = client.get("/businesses", headers=bearer(second["access_token"]))
    other_business_id = second_businesses.json()[0]["id"]

    response = client.get(
        f"/businesses/{other_business_id}/transactions",
        headers=bearer(first["access_token"]),
    )
    assert response.status_code == 404


def test_transaction_routes_require_auth_and_support_lifecycle(
    client: TestClient,
) -> None:
    anonymous_url = "/businesses/00000000-0000-0000-0000-000000000000/transactions"
    assert client.get(anonymous_url).status_code == 401

    account = register(client, "ledger@example.com")
    headers = bearer(account["access_token"])
    business = client.get("/businesses", headers=headers).json()[0]
    payload = {
        "business_id": business["id"],
        "direction": "income",
        "amount": "1250.50",
        "currency_code": "NGN",
        "transaction_date": "2026-10-18",
        "description": "Daily sales",
        "category": "Sales",
        "status": "posted",
    }
    created = client.post(
        f"/businesses/{business['id']}/transactions",
        headers=headers,
        json=payload,
    )
    assert created.status_code == 201, created.text
    transaction_id = created.json()["id"]

    listed = client.get(
        f"/businesses/{business['id']}/transactions",
        headers=headers,
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    voided = client.post(
        f"/businesses/{business['id']}/transactions/{transaction_id}/void",
        headers=headers,
    )
    assert voided.status_code == 200
    assert voided.json()["status"] == "void"


def test_invalid_and_expired_access_tokens_are_rejected(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert client.get("/auth/me", headers=bearer("not-a-valid-token")).status_code == 401
    result = register(client, "expiry@example.com")
    monkeypatch.setattr("app.access_tokens.TOKEN_TTL_SECONDS", -1)
    response = client.get("/auth/me", headers=bearer(result["access_token"]))
    assert response.status_code == 401



def test_registration_defaults_to_private_solo_and_business_is_separate(
    client: TestClient,
) -> None:
    response = client.post(
        "/auth/register",
        json={
            "email": "solo@example.com",
            "password": "correct-horse-battery-7",
        },
    )
    assert response.status_code == 201, response.text
    headers = bearer(response.json()["access_token"])

    initial = client.get("/businesses", headers=headers)
    assert initial.status_code == 200
    assert len(initial.json()) == 1
    solo = initial.json()[0]
    assert solo["workspace_type"] == "solo"
    assert solo["name"] == "My Solo Workspace"

    created = client.post(
        "/businesses",
        headers=headers,
        json={
            "name": "Goggles CEO Trading",
            "display_name": "Goggles CEO",
            "organization_label": "Teams",
            "currency_code": "NGN",
            "timezone": "Africa/Lagos",
        },
    )
    assert created.status_code == 201, created.text
    business = created.json()
    assert business["workspace_type"] == "business"
    assert business["name"] == "Goggles CEO Trading"
    assert business["display_name"] == "Goggles CEO"
    assert business["organization_label"] == "Teams"

    workspaces = client.get("/businesses", headers=headers).json()
    assert len(workspaces) == 2
    assert {workspace["workspace_type"] for workspace in workspaces} == {"solo", "business"}
    assert solo["id"] in {workspace["id"] for workspace in workspaces}



def test_worker_permissions_limit_transaction_reads_and_writes(
    client: TestClient,
) -> None:
    from sqlalchemy import select

    from app.models import BusinessMembership

    account = register(client, "worker-permissions@example.com")
    headers = bearer(account["access_token"])
    business = client.get("/businesses", headers=headers).json()[0]
    business_id = business["id"]

    income = {
        "business_id": business_id,
        "direction": "income",
        "amount": "200.00",
        "currency_code": "NGN",
        "transaction_date": "2026-10-18",
        "description": "Recorded sale",
        "category": "Sales",
        "status": "posted",
    }
    expense = {
        **income,
        "direction": "expense",
        "description": "Private expense",
        "category": "Supplies",
    }
    created_income = client.post(
        f"/businesses/{business_id}/transactions", headers=headers, json=income
    )
    created_expense = client.post(
        f"/businesses/{business_id}/transactions", headers=headers, json=expense
    )
    assert created_income.status_code == 201, created_income.text
    assert created_expense.status_code == 201, created_expense.text

    with client.app.state.test_session() as db:
        membership = db.scalar(
            select(BusinessMembership).where(
                BusinessMembership.business_id == business_id
            )
        )
        assert membership is not None
        membership.role = "worker"
        membership.permissions = {"sales:read": True, "sales:write": True}
        db.commit()
        income_id = created_income.json()["id"]
        expense_id = created_expense.json()["id"]

    listed = client.get(f"/businesses/{business_id}/transactions", headers=headers)
    assert listed.status_code == 200, listed.text
    assert [item["direction"] for item in listed.json()] == ["income"]

    denied_read = client.get(
        f"/businesses/{business_id}/transactions/{expense_id}", headers=headers
    )
    assert denied_read.status_code == 403

    denied_expense_create = client.post(
        f"/businesses/{business_id}/transactions",
        headers=headers,
        json={**expense, "description": "Attempted unauthorized expense"},
    )
    assert denied_expense_create.status_code == 403

    allowed_income_create = client.post(
        f"/businesses/{business_id}/transactions",
        headers=headers,
        json={**income, "description": "Authorized additional sale"},
    )
    assert allowed_income_create.status_code == 201, allowed_income_create.text

    denied_expense_update = client.patch(
        f"/businesses/{business_id}/transactions/{expense_id}",
        headers=headers,
        json={"description": "Unauthorized change"},
    )
    assert denied_expense_update.status_code == 403

    denied_expense_void = client.post(
        f"/businesses/{business_id}/transactions/{expense_id}/void",
        headers=headers,
    )
    assert denied_expense_void.status_code == 403
