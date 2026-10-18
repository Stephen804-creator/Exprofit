"""Security tests for recipient-bound workspace invitations."""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import UUID
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import BusinessMembership, User, WorkspaceInvitation


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    """Run invitation API requests against an isolated database."""
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
        json={"name": "Shared Shop", "display_name": "Shared Shop"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def verify_user_email(client: TestClient, email: str) -> None:
    with client.app.state.test_session() as db:
        user = db.scalar(select(User).where(User.email == email))
        assert user is not None
        user.email_verified = True
        db.commit()


def configure_mail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "no-reply@example.test")
    monkeypatch.setenv("SMTP_STARTTLS", "false")
    get_settings.cache_clear()


def test_invitation_is_recipient_bound_verified_single_use_and_hashed(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_mail(monkeypatch)
    owner = register(client, "owner@example.test")
    recipient = register(client, "recipient@example.test")
    wrong_user = register(client, "wrong@example.test")
    business_id = make_business(client, owner["access_token"])
    delivered: dict[str, str] = {}

    def capture_email(
        email: str,
        invitation_url: str,
        workspace_name: str,
        settings: object,
    ) -> None:
        delivered["email"] = email
        delivered["url"] = invitation_url

    monkeypatch.setattr("app.api.routes.invitations.send_invitation_email", capture_email)
    created = client.post(
        f"/businesses/{business_id}/invitations",
        headers=bearer(owner["access_token"]),
        json={
            "recipient_email": "Recipient@Example.test",
            "role": "worker",
            "permissions": {"sales:read": True, "sales:write": True},
        },
    )
    assert created.status_code == 201, created.text
    assert delivered["email"] == "recipient@example.test"
    assert "token" not in created.json()

    raw_token = parse_qs(urlparse(delivered["url"]).query)["token"][0]
    with client.app.state.test_session() as db:
        record = db.get(WorkspaceInvitation, created.json()["id"])
        assert record is not None
        assert record.token_hash != raw_token
        assert len(record.token_hash) == 64

    not_verified = client.post(
        "/invitations/accept",
        headers=bearer(recipient["access_token"]),
        json={"token": raw_token},
    )
    assert not_verified.status_code == 403

    verify_user_email(client, "wrong@example.test")
    wrong_email = client.post(
        "/invitations/accept",
        headers=bearer(wrong_user["access_token"]),
        json={"token": raw_token},
    )
    assert wrong_email.status_code == 403

    verify_user_email(client, "recipient@example.test")
    accepted = client.post(
        "/invitations/accept",
        headers=bearer(recipient["access_token"]),
        json={"token": raw_token},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json() == {
        "business_id": business_id,
        "role": "worker",
        "status": "active",
    }

    with client.app.state.test_session() as db:
        membership = db.scalar(
            select(BusinessMembership).where(
                BusinessMembership.business_id == accepted.json()["business_id"],
                BusinessMembership.user_id == db.scalar(
                    select(User.id).where(User.email == "recipient@example.test")
                ),
            )
        )
        assert membership is not None
        assert membership.permissions == {"sales:read": True, "sales:write": True}

    replay = client.post(
        "/invitations/accept",
        headers=bearer(recipient["access_token"]),
        json={"token": raw_token},
    )
    assert replay.status_code == 400


def test_revoked_invitation_cannot_be_accepted(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_mail(monkeypatch)
    owner = register(client, "owner-revoke@example.test")
    recipient = register(client, "revoked-recipient@example.test")
    business_id = make_business(client, owner["access_token"])
    delivered: dict[str, str] = {}

    def capture_email(
        email: str,
        invitation_url: str,
        workspace_name: str,
        settings: object,
    ) -> None:
        delivered["url"] = invitation_url

    monkeypatch.setattr("app.api.routes.invitations.send_invitation_email", capture_email)
    created = client.post(
        f"/businesses/{business_id}/invitations",
        headers=bearer(owner["access_token"]),
        json={"recipient_email": "revoked-recipient@example.test", "role": "worker"},
    )
    assert created.status_code == 201, created.text
    token = parse_qs(urlparse(delivered["url"]).query)["token"][0]

    revoked = client.post(
        f"/businesses/{business_id}/invitations/{created.json()['id']}/revoke",
        headers=bearer(owner["access_token"]),
    )
    assert revoked.status_code == 204

    verify_user_email(client, "revoked-recipient@example.test")
    accepted = client.post(
        "/invitations/accept",
        headers=bearer(recipient["access_token"]),
        json={"token": token},
    )
    assert accepted.status_code == 400


def test_worker_cannot_create_workspace_invitations(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_mail(monkeypatch)
    owner = register(client, "owner-worker-test@example.test")
    worker = register(client, "worker@example.test")
    business_id = make_business(client, owner["access_token"])
    with client.app.state.test_session() as db:
        worker_user = db.scalar(select(User).where(User.email == "worker@example.test"))
        assert worker_user is not None
        membership = BusinessMembership(
            user_id=worker_user.id,
            business_id=UUID(business_id),
            role="worker",
            status="active",
            permissions={"sales:read": True},
        )
        db.add(membership)
        db.commit()

    response = client.post(
        f"/businesses/{business_id}/invitations",
        headers=bearer(worker["access_token"]),
        json={"recipient_email": "someone@example.test", "role": "worker"},
    )
    assert response.status_code == 403



def test_expired_invitation_cannot_be_accepted(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_mail(monkeypatch)
    owner = register(client, "owner-expiry@example.test")
    recipient = register(client, "expired-recipient@example.test")
    business_id = make_business(client, owner["access_token"])
    delivered: dict[str, str] = {}

    def capture_email(
        email: str,
        invitation_url: str,
        workspace_name: str,
        settings: object,
    ) -> None:
        delivered["url"] = invitation_url

    monkeypatch.setattr("app.api.routes.invitations.send_invitation_email", capture_email)
    created = client.post(
        f"/businesses/{business_id}/invitations",
        headers=bearer(owner["access_token"]),
        json={"recipient_email": "expired-recipient@example.test", "role": "worker"},
    )
    assert created.status_code == 201, created.text
    token = parse_qs(urlparse(delivered["url"]).query)["token"][0]

    with client.app.state.test_session() as db:
        invitation = db.get(WorkspaceInvitation, created.json()["id"])
        assert invitation is not None
        invitation.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()

    verify_user_email(client, "expired-recipient@example.test")
    response = client.post(
        "/invitations/accept",
        headers=bearer(recipient["access_token"]),
        json={"token": token},
    )
    assert response.status_code == 400
