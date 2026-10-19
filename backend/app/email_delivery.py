"""SMTP delivery for account verification messages."""

import smtplib
from datetime import datetime
from email.message import EmailMessage

from app.config import Settings


class EmailDeliveryError(RuntimeError):
    """Raised when a verification message cannot be delivered."""


def send_verification_email(
    recipient: str,
    verification_url: str,
    settings: Settings,
) -> None:
    """Send a verification link without logging or returning the raw token."""
    if not settings.email_delivery_configured:
        raise EmailDeliveryError("Email delivery is not configured")

    message = EmailMessage()
    message["Subject"] = "Verify your Exprofit email address"
    message["From"] = settings.smtp_from_email
    message["To"] = recipient
    message.set_content(
        "Verify your email address to use Exprofit collaboration features.\n\n"
        f"Open this link to verify your address: {verification_url}\n\n"
        f"This link expires in {settings.email_verification_ttl_minutes} minutes. "
        "If you did not request this message, you can ignore it."
    )

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            server.ehlo()
            if settings.smtp_starttls:
                server.starttls()
                server.ehlo()
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise EmailDeliveryError("Verification email could not be sent") from exc


def send_invitation_email(
    recipient: str,
    invitation_url: str,
    workspace_name: str,
    settings: Settings,
    expires_at: datetime | None = None,
) -> None:
    """Send a recipient-bound invitation without exposing the token in API output."""
    if not settings.email_delivery_configured:
        raise EmailDeliveryError("Email delivery is not configured")

    message = EmailMessage()
    message["Subject"] = f"Invitation to join {workspace_name} on Exprofit"
    message["From"] = settings.smtp_from_email
    message["To"] = recipient
    message.set_content(
        f"You have been invited to join the {workspace_name} workspace on Exprofit.\n\n"
        f"Review and accept the invitation here: {invitation_url}\n\n"
        (f"This invitation expires at {expires_at.isoformat()} (UTC). " if expires_at else "")
        "You must sign in with the exact email address that received this invitation, "
        "and that email address must be verified. If you were not expecting this invite, "
        "you can ignore this message."
    )

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            server.ehlo()
            if settings.smtp_starttls:
                server.starttls()
                server.ehlo()
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise EmailDeliveryError("Invitation email could not be sent") from exc
