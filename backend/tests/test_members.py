"""Tests for member permissions, suspension lifecycle, and audit history."""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
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
from app.models import AuditEvent, BusinessMembership, User


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    """Run member administration requests against an isolated database."""
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
        json={"name": "Member Test Shop"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def add_worker(client: TestClient, business_id: str, email: str) -> tuple[dict, UUID]:
    account = register(client, email)
    with client.app.state.test_session() as db:
        user = db.scalar(select(User).where(User.email == email))
        assert user is not None
        membership = BusinessMembership(
            user_id=user.id,
            business_id=UUID(business_id),
            role="worker",
            status="active",
            permissions={"sales:read": True},
        )
        db.add(membership)
        db.commit()
        membership_id = membership.id
    return account, membership_id


def test_owner_can_manage_members_and_read_audit_history(client: TestClient) -> None:
    owner = register(client, "member-owner@example.com")
    business_id = make_business(client, owner["access_token"])
    worker, membership_id = add_worker(client, business_id, "member-worker@example.com")

    listed = client.get(
        f"/businesses/{business_id}/members",
        headers=bearer(owner["access_token"]),
    )
    assert listed.status_code == 200, listed.text
    assert {member["email"] for member in listed.json()} == {
        "member-owner@example.com",
        "member-worker@example.com",
    }

    updated = client.patch(
        f"/businesses/{business_id}/members/{membership_id}",
        headers=bearer(owner["access_token"]),
        json={
            "role": "worker",
            "permissions": {"sales:read": True, "expenses:read": True},
            "reason": "Assign sales and expense review responsibilities",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["permissions"] == {
        "sales:read": True,
        "expenses:read": True,
    }

    events = client.get(
        f"/businesses/{business_id}/audit-events",
        headers=bearer(owner["access_token"]),
    )
    assert events.status_code == 200, events.text
    event_types = {event["event_type"] for event in events.json()}
    assert "workspace.created" in event_types
    assert "membership.updated" in event_types
    assert "metadata" in events.json()[0]


def test_timed_suspension_blocks_access_then_auto_reinstates(
    client: TestClient,
) -> None:
    owner = register(client, "suspension-owner@example.com")
    business_id = make_business(client, owner["access_token"])
    worker, membership_id = add_worker(client, business_id, "suspension-worker@example.com")

    suspended = client.post(
        f"/businesses/{business_id}/members/{membership_id}/suspend",
        headers=bearer(owner["access_token"]),
        json={"reason": "Temporary access review", "duration_hours": 1},
    )
    assert suspended.status_code == 200, suspended.text
    assert suspended.json()["status"] == "suspended"
    assert client.get(
        f"/businesses/{business_id}/transactions",
        headers=bearer(worker["access_token"]),
    ).status_code == 404

    with client.app.state.test_session() as db:
        membership = db.get(BusinessMembership, membership_id)
        assert membership is not None
        membership.suspended_until = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()

    access = client.get(
        f"/businesses/{business_id}/transactions",
        headers=bearer(worker["access_token"]),
    )
    assert access.status_code == 200, access.text

    with client.app.state.test_session() as db:
        events = db.scalars(
            select(AuditEvent).where(
                AuditEvent.business_id == UUID(business_id),
                AuditEvent.event_type == "membership.auto_reinstated",
            )
        ).all()
        assert len(events) == 1


def test_revoked_member_loses_access_and_cannot_be_manually_reinstated(
    client: TestClient,
) -> None:
    owner = register(client, "revoke-owner@example.com")
    business_id = make_business(client, owner["access_token"])
    worker, membership_id = add_worker(client, business_id, "revoke-worker@example.com")

    revoked = client.post(
        f"/businesses/{business_id}/members/{membership_id}/revoke",
        headers=bearer(owner["access_token"]),
        json={"reason": "Employment ended"},
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["status"] == "revoked"
    assert client.get(
        f"/businesses/{business_id}/transactions",
        headers=bearer(worker["access_token"]),
    ).status_code == 404

    reinstated = client.post(
        f"/businesses/{business_id}/members/{membership_id}/reinstate",
        headers=bearer(owner["access_token"]),
        json={"reason": "Try to restore revoked membership"},
    )
    assert reinstated.status_code == 409


def test_worker_cannot_view_member_directory_or_audit_log(client: TestClient) -> None:
    owner = register(client, "directory-owner@example.com")
    business_id = make_business(client, owner["access_token"])
    worker, _ = add_worker(client, business_id, "directory-worker@example.com")

    members = client.get(
        f"/businesses/{business_id}/members",
        headers=bearer(worker["access_token"]),
    )
    audit = client.get(
        f"/businesses/{business_id}/audit-events",
        headers=bearer(worker["access_token"]),
    )
    assert members.status_code == 403
    assert audit.status_code == 403



def test_voluntary_leave_requires_exact_phrase_and_password(
    client: TestClient,
) -> None:
    owner = register(client, "leave-owner@example.com")
    business_id = make_business(client, owner["access_token"])
    worker, membership_id = add_worker(client, business_id, "leave-worker@example.com")
    endpoint = f"/businesses/{business_id}/leave"
    headers = bearer(worker["access_token"])

    wrong_phrase = client.post(
        endpoint,
        headers=headers,
        json={
            "confirmation_phrase": "I want to Leave",
            "password": "correct-horse-battery-7",
            "reason": "Leaving this team",
        },
    )
    assert wrong_phrase.status_code == 422

    wrong_password = client.post(
        endpoint,
        headers=headers,
        json={
            "confirmation_phrase": "I want to leave",
            "password": "wrong-password",
            "reason": "Leaving this team",
        },
    )
    assert wrong_password.status_code == 401

    left = client.post(
        endpoint,
        headers=headers,
        json={
            "confirmation_phrase": "I want to leave",
            "password": "correct-horse-battery-7",
            "reason": "Leaving this team",
        },
    )
    assert left.status_code == 200, left.text
    assert left.json()["status"] == "revoked"
    assert client.get(
        f"/businesses/{business_id}/transactions",
        headers=headers,
    ).status_code == 404

    with client.app.state.test_session() as db:
        membership = db.get(BusinessMembership, membership_id)
        assert membership is not None
        assert membership.status == "revoked"
        assert membership.leave_reason == "Leaving this team"
        events = db.scalars(
            select(AuditEvent).where(
                AuditEvent.business_id == UUID(business_id),
                AuditEvent.event_type == "membership.left",
            )
        ).all()
        assert len(events) == 1


def test_scheduled_leave_revokes_access_at_effective_time(
    client: TestClient,
) -> None:
    owner = register(client, "scheduled-owner@example.com")
    business_id = make_business(client, owner["access_token"])
    worker, membership_id = add_worker(client, business_id, "scheduled-worker@example.com")
    headers = bearer(worker["access_token"])

    scheduled = client.post(
        f"/businesses/{business_id}/leave",
        headers=headers,
        json={
            "confirmation_phrase": "I want to leave",
            "password": "correct-horse-battery-7",
            "reason": "Providing handover notice",
            "notice_hours": 2,
        },
    )
    assert scheduled.status_code == 200, scheduled.text
    assert scheduled.json()["status"] == "scheduled"
    assert client.get(
        f"/businesses/{business_id}/transactions",
        headers=headers,
    ).status_code == 200

    with client.app.state.test_session() as db:
        membership = db.get(BusinessMembership, membership_id)
        assert membership is not None
        membership.leave_effective_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()

    denied = client.get(
        f"/businesses/{business_id}/transactions",
        headers=headers,
    )
    assert denied.status_code == 404


def test_workspace_owner_cannot_leave_without_ownership_transfer(
    client: TestClient,
) -> None:
    owner = register(client, "owner-cannot-leave@example.com")
    business_id = make_business(client, owner["access_token"])
    response = client.post(
        f"/businesses/{business_id}/leave",
        headers=bearer(owner["access_token"]),
        json={
            "confirmation_phrase": "I want to leave",
            "password": "correct-horse-battery-7",
            "reason": "Owner departure",
        },
    )
    assert response.status_code == 409
