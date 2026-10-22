"""Integration tests for the receipt and financial API workflow."""

from collections.abc import Generator
from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import Receipt, Transaction


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
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


def register(client: TestClient, email: str) -> dict:
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "correct-horse-battery-7"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def make_business(client: TestClient, token: str) -> str:
    response = client.post(
        "/businesses",
        headers=bearer(token),
        json={"name": "Test Shop", "display_name": "Test Shop"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def upload_receipt(client: TestClient, token: str, business_id: str):
    # Signature fixture intentionally isn't a decodable photo; OCR is best-effort.
    fake_jpeg = bytes((0xFF, 0xD8, 0xFF)) + (b"test-image-data-" * 20)
    return client.post(
        f"/businesses/{business_id}/receipts",
        headers=bearer(token),
        files={"file": ("receipt.jpg", fake_jpeg, "image/jpeg")},
    )


def test_receipt_requires_explicit_confirmation_before_transaction_creation(
    client: TestClient,
) -> None:
    owner = register(client, "receipt-owner@example.com")
    business_id = make_business(client, owner["access_token"])
    uploaded = upload_receipt(client, owner["access_token"], business_id)
    assert uploaded.status_code == 201, uploaded.text
    receipt = uploaded.json()
    assert receipt["review_status"] == "pending"
    assert receipt["linked_transaction_id"] is None

    with client.app.state.test_session() as db:
        assert db.scalars(select(Transaction)).all() == []

    file_response = client.get(
        f"/businesses/{business_id}/receipts/{receipt['id']}/file",
        headers=bearer(owner["access_token"]),
    )
    assert file_response.status_code == 200
    assert file_response.headers["cache-control"] == "private, no-store"
    assert file_response.headers["x-content-type-options"] == "nosniff"
    assert file_response.headers["content-disposition"].startswith("attachment;")

    blank_description = client.post(
        f"/businesses/{business_id}/receipts/{receipt['id']}/confirm",
        headers=bearer(owner["access_token"]),
        json={
            "direction": "expense",
            "amount": "125.50",
            "transaction_date": "2026-10-18",
            "description": "   ",
            "category": "COGS",
        },
    )
    assert blank_description.status_code == 422

    confirmed = client.post(
        f"/businesses/{business_id}/receipts/{receipt['id']}/confirm",
        headers=bearer(owner["access_token"]),
        json={
            "direction": "expense",
            "amount": "125.50",
            "transaction_date": "2026-10-18",
            "description": "Reviewed stock purchase",
            "category": "COGS",
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    payload = confirmed.json()
    assert payload["receipt"]["review_status"] == "confirmed"
    assert payload["transaction_id"] == payload["receipt"]["linked_transaction_id"]

    with client.app.state.test_session() as db:
        rows = db.scalars(select(Transaction)).all()
        assert len(rows) == 1
        assert rows[0].amount == Decimal("125.50")
        assert rows[0].description == "Reviewed stock purchase"
        assert rows[0].status == "posted"

    replay = client.post(
        f"/businesses/{business_id}/receipts/{receipt['id']}/confirm",
        headers=bearer(owner["access_token"]),
        json={
            "direction": "expense",
            "amount": "125.50",
            "transaction_date": "2026-10-18",
            "description": "Duplicate attempt",
            "category": "COGS",
        },
    )
    assert replay.status_code == 409


def test_rejected_receipt_file_and_extracted_text_are_cleared(client: TestClient) -> None:
    owner = register(client, "receipt-reject@example.com")
    business_id = make_business(client, owner["access_token"])
    uploaded = upload_receipt(client, owner["access_token"], business_id)
    assert uploaded.status_code == 201, uploaded.text
    receipt_id = uploaded.json()["id"]

    rejected = client.post(
        f"/businesses/{business_id}/receipts/{receipt_id}/reject",
        headers=bearer(owner["access_token"]),
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["review_status"] == "rejected"

    file_response = client.get(
        f"/businesses/{business_id}/receipts/{receipt_id}/file",
        headers=bearer(owner["access_token"]),
    )
    assert file_response.status_code == 404

    with client.app.state.test_session() as db:
        receipt = db.get(Receipt, UUID(receipt_id))
        assert receipt is not None
        assert receipt.file_bytes == b""
        assert receipt.extracted_text == ""


def test_receipt_upload_rejects_mismatched_file_signature(client: TestClient) -> None:
    owner = register(client, "receipt-invalid@example.com")
    business_id = make_business(client, owner["access_token"])
    response = client.post(
        f"/businesses/{business_id}/receipts",
        headers=bearer(owner["access_token"]),
        files={"file": ("not-really.jpg", b"not a jpeg file", "image/jpeg")},
    )
    assert response.status_code == 415


def test_duplicate_receipt_upload_is_rejected(client: TestClient) -> None:
    owner = register(client, "receipt-duplicate@example.com")
    business_id = make_business(client, owner["access_token"])
    first = upload_receipt(client, owner["access_token"], business_id)
    assert first.status_code == 201, first.text

    duplicate = upload_receipt(client, owner["access_token"], business_id)
    assert duplicate.status_code == 409
    assert "already been uploaded" in duplicate.json()["detail"]


def test_financial_brief_falls_back_without_hugging_face_token(client: TestClient, monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "")
    get_settings.cache_clear()
    owner = register(client, "brief-owner@example.com")
    business_id = make_business(client, owner["access_token"])
    headers = bearer(owner["access_token"])
    for direction, amount, category in (
        ("income", "100000.00", "Sales"),
        ("expense", "40000.00", "COGS"),
    ):
        response = client.post(
            f"/businesses/{business_id}/transactions",
            headers=headers,
            json={
                "business_id": business_id,
                "direction": direction,
                "amount": amount,
                "currency_code": "NGN",
                "transaction_date": "2026-10-18",
                "description": f"Test {direction}",
                "category": category,
                "status": "posted",
            },
        )
        assert response.status_code == 201, response.text

    brief = client.post(
        f"/businesses/{business_id}/financial-brief",
        headers=headers,
        json={"end_date": "2026-10-19", "period_days": 30, "use_ai": True},
    )
    assert brief.status_code == 200, brief.text
    assert brief.json()["provider"] == "rules"
    assert brief.json()["ai_status"] == "not_configured"
    assert brief.json()["ai_is_authoritative"] is False
    assert "verified_facts" in brief.json()


def test_what_if_endpoint_is_authenticated_and_does_not_change_ledger(client: TestClient):
    owner = register(client, "what-if-owner@example.com")
    business_id = make_business(client, owner["access_token"])
    headers = bearer(owner["access_token"])
    for direction, amount, category in (
        ("income", "100000.00", "Sales"),
        ("expense", "40000.00", "COGS"),
    ):
        response = client.post(
            f"/businesses/{business_id}/transactions",
            headers=headers,
            json={
                "business_id": business_id,
                "direction": direction,
                "amount": amount,
                "currency_code": "NGN",
                "transaction_date": "2026-10-18",
                "description": f"Test {direction}",
                "category": category,
                "status": "posted",
            },
        )
        assert response.status_code == 201, response.text

    with client.app.state.test_session() as db:
        before_count = len(db.scalars(select(Transaction)).all())

    result = client.post(
        f"/businesses/{business_id}/what-if",
        headers=headers,
        json={
            "end_date": "2026-10-19",
            "period_days": 30,
            "price_change_percent": "10",
            "volume_change_percent": "20",
            "unit_cost_change_percent": "5",
        },
    )
    assert result.status_code == 200, result.text
    row = result.json()["results"][0]
    assert row["estimated_revenue"] == "132000.00"
    assert row["estimated_direct_costs"] == "50400.00"
    assert row["estimated_gross_profit"] == "81600.00"
    assert result.json()["persisted"] is False

    with client.app.state.test_session() as db:
        assert len(db.scalars(select(Transaction)).all()) == before_count


def test_financial_brief_cannot_be_read_from_another_users_workspace(client: TestClient):
    owner = register(client, "brief-private-owner@example.com")
    other = register(client, "brief-private-other@example.com")
    business_id = make_business(client, owner["access_token"])
    response = client.post(
        f"/businesses/{business_id}/financial-brief",
        headers=bearer(other["access_token"]),
        json={"end_date": "2026-10-19", "period_days": 30},
    )
    assert response.status_code == 404


def test_financial_brief_falls_back_when_hugging_face_is_unavailable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    from app.api.routes import intelligence as intelligence_routes

    monkeypatch.setenv("HF_TOKEN", "test-only-token")
    get_settings.cache_clear()
    monkeypatch.setattr(intelligence_routes, "_call_gemma", lambda *args, **kwargs: None)
    owner = register(client, "brief-fallback@example.com")
    business_id = make_business(client, owner["access_token"])
    response = client.post(
        f"/businesses/{business_id}/financial-brief",
        headers=bearer(owner["access_token"]),
        json={"end_date": "2026-10-19", "period_days": 30, "use_ai": True},
    )
    assert response.status_code == 200, response.text
    assert response.json()["provider"] == "rules"
    assert response.json()["ai_status"] == "unavailable_fallback"
    assert response.json()["brief"]


def test_product_customer_attribution_and_profitability(client: TestClient) -> None:
    owner = register(client, "catalog-owner@example.com")
    token = owner["access_token"]
    business_id = make_business(client, token)
    headers = bearer(token)
    product_response = client.post(
        f"/businesses/{business_id}/products",
        headers=headers,
        json={
            "name": "Handmade Bag",
            "sku": "BAG-001",
            "unit_price": "1000.00",
            "unit_cost": "400.00",
        },
    )
    assert product_response.status_code == 201, product_response.text
    product_id = product_response.json()["id"]
    customer_response = client.post(
        f"/businesses/{business_id}/customers",
        headers=headers,
        json={"name": "Ada Buyer", "email": "ada@example.com"},
    )
    assert customer_response.status_code == 201, customer_response.text
    customer_id = customer_response.json()["id"]
    today = date.today().isoformat()

    income = client.post(
        f"/businesses/{business_id}/transactions",
        headers=headers,
        json={
            "business_id": business_id, "direction": "income", "amount": "1000.00",
            "currency_code": "NGN", "transaction_date": today, "description": "Bag sale",
            "category": "Sales", "status": "posted", "product_id": product_id,
            "customer_id": customer_id,
        },
    )
    assert income.status_code == 201, income.text
    cost = client.post(
        f"/businesses/{business_id}/transactions",
        headers=headers,
        json={
            "business_id": business_id, "direction": "expense", "amount": "400.00",
            "currency_code": "NGN", "transaction_date": today, "description": "Bag materials",
            "category": "COGS", "status": "posted", "product_id": product_id,
            "customer_id": customer_id,
        },
    )
    assert cost.status_code == 201, cost.text

    product_report = client.get(f"/businesses/{business_id}/product-profitability", headers=headers)
    customer_report = client.get(
        f"/businesses/{business_id}/customer-profitability", headers=headers
    )
    assert product_report.status_code == 200, product_report.text
    assert customer_report.status_code == 200, customer_report.text
    assert product_report.json()["items"][0]["revenue"] == "1000.00"
    assert product_report.json()["items"][0]["direct_costs"] == "400.00"
    assert product_report.json()["items"][0]["gross_profit"] == "600.00"
    assert customer_report.json()["items"][0]["gross_profit"] == "600.00"


def test_budget_vs_actual_uses_all_posted_matching_expenses(client: TestClient) -> None:
    owner = register(client, "budget-owner@example.com")
    token = owner["access_token"]
    business_id = make_business(client, token)
    headers = bearer(token)
    today = __import__("datetime").date.today().isoformat()
    budget = client.post(
        f"/businesses/{business_id}/budgets",
        headers=headers,
        json={
            "category": "Rent", "period_start": today, "period_end": today,
            "amount": "1000.00", "warning_threshold_percent": 80,
        },
    )
    assert budget.status_code == 201, budget.text
    for amount in ("300.00", "250.00"):
        response = client.post(
            f"/businesses/{business_id}/transactions",
            headers=headers,
            json={
                "business_id": business_id, "direction": "expense", "amount": amount,
                "currency_code": "NGN", "transaction_date": today, "description": "Rent",
                "category": "Rent", "status": "posted",
            },
        )
        assert response.status_code == 201, response.text
    result = client.get(f"/businesses/{business_id}/budget-vs-actual", headers=headers)
    assert result.status_code == 200, result.text
    row = result.json()["items"][0]
    assert row["actual_spend"] == "550.00"
    assert row["remaining"] == "450.00"
    assert row["status"] == "on_track"


def test_browser_security_headers_are_present(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert response.headers["permissions-policy"] == "camera=(self), microphone=(), geolocation=()"
    assert response.headers["x-frame-options"] == "DENY"


def test_transaction_cannot_reference_product_from_another_workspace(
    client: TestClient,
) -> None:
    owner = register(client, "workspace-attribution-owner@example.com")
    token = owner["access_token"]
    headers = bearer(token)
    first_workspace = make_business(client, token)
    second_workspace = make_business(client, token)
    product = client.post(
        f"/businesses/{first_workspace}/products",
        headers=headers,
        json={"name": "Private Product"},
    )
    assert product.status_code == 201, product.text
    response = client.post(
        f"/businesses/{second_workspace}/transactions",
        headers=headers,
        json={
            "business_id": second_workspace,
            "direction": "income",
            "amount": "10.00",
            "currency_code": "NGN",
            "transaction_date": date.today().isoformat(),
            "description": "Must not cross workspaces",
            "status": "posted",
            "product_id": product.json()["id"],
        },
    )
    assert response.status_code == 422
