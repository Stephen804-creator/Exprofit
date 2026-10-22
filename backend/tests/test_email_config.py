"""Tests for the minimum SMTP configuration required to send mail."""

from app.config import Settings


def test_email_delivery_requires_complete_smtp_credentials() -> None:
    settings = Settings(
        smtp_host="smtp-relay.brevo.com",
        smtp_port=587,
        smtp_username="smtp-login@example.com",
        smtp_password="example-test-key",
        smtp_from_email="verified@example.com",
    )
    assert settings.email_delivery_configured


def test_email_delivery_is_not_configured_when_smtp_password_is_missing() -> None:
    settings = Settings(
        smtp_host="smtp-relay.brevo.com",
        smtp_port=587,
        smtp_username="smtp-login@example.com",
        smtp_password="",
        smtp_from_email="verified@example.com",
    )
    assert not settings.email_delivery_configured


def test_email_delivery_is_not_configured_when_sender_is_missing() -> None:
    settings = Settings(
        smtp_host="smtp-relay.brevo.com",
        smtp_port=587,
        smtp_username="smtp-login@example.com",
        smtp_password="example-test-key",
        smtp_from_email="",
    )
    assert not settings.email_delivery_configured
