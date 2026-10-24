"""Unit tests for SMTP message construction without contacting a mail provider."""

import logging
from datetime import UTC, datetime
from email.message import EmailMessage
from smtplib import SMTPAuthenticationError
from unittest.mock import patch

from app.config import Settings
from app.email_delivery import EmailDeliveryError, send_invitation_email


class FakeSMTP:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        self.message: EmailMessage | None = None

    def __enter__(self) -> "FakeSMTP":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def ehlo(self) -> None:
        return None

    def starttls(self) -> None:
        return None

    def login(self, _username: str, _password: str) -> None:
        return None

    def send_message(self, message: EmailMessage) -> None:
        self.message = message


def test_invitation_email_body_includes_link_and_expiry() -> None:
    settings = Settings(
        smtp_host="smtp-relay.brevo.com",
        smtp_port=587,
        smtp_username="smtp-login@example.com",
        smtp_password="test-smtp-password",
        smtp_from_email="verified@example.com",
        smtp_starttls=False,
    )
    fake_server = FakeSMTP()
    with patch("app.email_delivery.smtplib.SMTP", return_value=fake_server):
        send_invitation_email(
            "recipient@example.com",
            "https://exprofit.onrender.com/accept-invitation?token=example",
            "Demo Workspace",
            settings,
            expires_at=datetime(2026, 10, 23, tzinfo=UTC),
        )

    assert fake_server.message is not None
    assert fake_server.message["To"] == "recipient@example.com"
    body = fake_server.message.get_content()
    assert "https://exprofit.onrender.com/accept-invitation?token=example" in body
    assert "This invitation expires at 2026-10-23T00:00:00+00:00 (UTC)." in body
    assert "must sign in with the exact email address" in body


def test_invitation_email_failure_logs_safe_smtp_diagnostic(caplog) -> None:
    settings = Settings(
        smtp_host="smtp-relay.brevo.com",
        smtp_port=587,
        smtp_username="smtp-login@example.com",
        smtp_password="test-smtp-password",
        smtp_from_email="verified@example.com",
        smtp_starttls=False,
    )
    with patch(
        "app.email_delivery.smtplib.SMTP",
        side_effect=SMTPAuthenticationError(
            535, b"Authentication failed for sender@example.com"
        ),
    ):
        with caplog.at_level(logging.WARNING, logger="app.email_delivery"):
            try:
                send_invitation_email(
                    "recipient@example.com",
                    "https://exprofit.example/accept-invitation?token=secret-token",
                    "Demo Workspace",
                    settings,
                )
            except EmailDeliveryError:
                pass
            else:
                raise AssertionError("Expected delivery failure")

    assert "SMTPAuthenticationError" in caplog.text
    assert "smtp_code=535" in caplog.text
    assert "[email redacted]" in caplog.text
    assert "recipient@example.com" not in caplog.text
    assert "test-smtp-password" not in caplog.text
    assert "secret-token" not in caplog.text
