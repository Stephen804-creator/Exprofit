"""Tests for the no-email, owner-reviewed invitation workflow."""

import base64
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse
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
from app.models import BusinessMembership, InvitationApplication, User, WorkspaceInvitation


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
        json={"name": "Shared Shop", "display_name": "Shared Shop"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def make_invitation(client: TestClient, owner_token: str, business_id: str, hours: int = 24) -> str:
    response = client.post(
        f"/businesses/{business_id}/invitations",
        headers=bearer(owner_token),
        json={"role": "worker", "permissions": {"sales:read": True}, "expires_in_hours": hours},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["invitation_url"]
    assert payload["recipient_email"] is None
    assert payload["expires_at"]
    return parse_qs(urlparse(payload["invitation_url"]).query)["token"][0]


def photo_data_url() -> str:
    # Minimal JPEG-signature fixture for API validation; not a real person's image.
    fake_jpeg = b"\xff\xd8\xff" + (b"test-image-data-" * 20)
    return "data:image/jpeg;base64," + base64.b64encode(fake_jpeg).decode("ascii")


def submit_application(client: TestClient, token: str, invite_token: str) -> dict:
    response = client.post(
        "/invitations/apply",
        headers=bearer(token),
        json={
            "token": invite_token,
            "full_name": "Test Applicant",
            "phone": "+2348000000000",
            "identifying_details": "We met at the shop on Monday and discussed the cashier role.",
            "photo_data_url": photo_data_url(),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_owner_reviews_application_before_membership_is_granted(client: TestClient) -> None:
    owner = register(client, "owner@example.com")
    applicant = register(client, "applicant@example.com")
    business_id = make_business(client, owner["access_token"])
    invite_token = make_invitation(client, owner["access_token"], business_id, hours=48)

    submitted = submit_application(client, applicant["access_token"], invite_token)
    application_id = submitted["id"]
    assert submitted["status"] == "pending"

    with client.app.state.test_session() as db:
        invitation = db.scalar(select(WorkspaceInvitation).where(WorkspaceInvitation.business_id == UUID(business_id)))
        assert invitation is not None
        assert invitation.token_hash != invite_token
        assert len(invitation.token_hash) == 64
        assert db.scalar(select(BusinessMembership).where(
            BusinessMembership.business_id == UUID(business_id),
            BusinessMembership.user_id == db.scalar(select(User.id).where(User.email == "applicant@example.com")),
        )) is None
        application = db.get(InvitationApplication, UUID(application_id))
        assert application is not None and application.photo_bytes is not None

    listed = client.get(
        f"/businesses/{business_id}/invitation-applications",
        headers=bearer(owner["access_token"]),
    )
    assert listed.status_code == 200, listed.text
    assert len(listed.json()) == 1
    photo = client.get(
        f"/businesses/{business_id}/invitation-applications/{application_id}/photo",
        headers=bearer(owner["access_token"]),
    )
    assert photo.status_code == 200
    assert photo.headers["cache-control"] == "private, no-store"

    approved = client.post(
        f"/businesses/{business_id}/invitation-applications/{application_id}/approve",
        headers=bearer(owner["access_token"]),
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    with client.app.state.test_session() as db:
        membership = db.scalar(select(BusinessMembership).where(
            BusinessMembership.business_id == UUID(business_id),
            BusinessMembership.user_id == db.scalar(select(User.id).where(User.email == "applicant@example.com")),
        ))
        assert membership is not None and membership.status == "active"
        application = db.get(InvitationApplication, UUID(application_id))
        assert application is not None and application.photo_bytes is None

    replay = client.post(
        "/invitations/apply",
        headers=bearer(applicant["access_token"]),
        json={
            "token": invite_token,
            "full_name": "Test Applicant",
            "identifying_details": "Repeated application attempt",
            "photo_data_url": photo_data_url(),
        },
    )
    assert replay.status_code == 400


def test_invitation_link_can_be_revoked_without_email_setup(client: TestClient) -> None:
    owner = register(client, "owner-revoke@example.com")
    applicant = register(client, "applicant-revoke@example.com")
    business_id = make_business(client, owner["access_token"])
    created = client.post(
        f"/businesses/{business_id}/invitations",
        headers=bearer(owner["access_token"]),
        json={"role": "worker", "expires_in_hours": 1},
    )
    assert created.status_code == 201, created.text
    token = parse_qs(urlparse(created.json()["invitation_url"]).query)["token"][0]

    revoked = client.post(
        f"/businesses/{business_id}/invitations/{created.json()['id']}/revoke",
        headers=bearer(owner["access_token"]),
    )
    assert revoked.status_code == 204
    rejected = client.post(
        "/invitations/apply",
        headers=bearer(applicant["access_token"]),
        json={
            "token": token,
            "full_name": "Applicant",
            "identifying_details": "We agreed to meet at the shop",
            "photo_data_url": photo_data_url(),
        },
    )
    assert rejected.status_code == 400


def test_expired_invitation_is_unusable(client: TestClient) -> None:
    owner = register(client, "owner-expiry@example.com")
    applicant = register(client, "applicant-expiry@example.com")
    business_id = make_business(client, owner["access_token"])
    token = make_invitation(client, owner["access_token"], business_id, hours=1)
    with client.app.state.test_session() as db:
        invitation = db.scalar(select(WorkspaceInvitation).where(WorkspaceInvitation.business_id == UUID(business_id)))
        assert invitation is not None
        invitation.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
    response = client.post(
        "/invitations/apply",
        headers=bearer(applicant["access_token"]),
        json={
            "token": token,
            "full_name": "Applicant",
            "identifying_details": "We agreed to meet at the shop",
            "photo_data_url": photo_data_url(),
        },
    )
    assert response.status_code == 400


def test_worker_cannot_create_invitation_or_review_applications(client: TestClient) -> None:
    owner = register(client, "owner-worker@example.com")
    worker = register(client, "worker@example.com")
    business_id = make_business(client, owner["access_token"])
    with client.app.state.test_session() as db:
        worker_user = db.scalar(select(User).where(User.email == "worker@example.com"))
        assert worker_user is not None
        db.add(BusinessMembership(
            user_id=worker_user.id, business_id=UUID(business_id), role="worker",
            status="active", permissions={"sales:read": True},
        ))
        db.commit()

    response = client.post(
        f"/businesses/{business_id}/invitations",
        headers=bearer(worker["access_token"]),
        json={"role": "worker"},
    )
    assert response.status_code == 403
    listing = client.get(
        f"/businesses/{business_id}/invitation-applications",
        headers=bearer(worker["access_token"]),
    )
    assert listing.status_code == 403
