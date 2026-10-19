"""Integration tests for the receipt and financial API workflow."""

from collections.abc import Generator
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
