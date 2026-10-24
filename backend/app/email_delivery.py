"""SMTP delivery for account verification messages."""

import logging
import re
import smtplib
from datetime import datetime
from email.message import EmailMessage

from app.config import Settings

logger = logging.getLogger(__name__)


def _smtp_failure_summary(exc: Exception) -> str:
    """Return a useful SMTP diagnostic without logging addresses or credentials."""
    detail = getattr(exc, "smtp_error", None) or str(exc)
    if isinstance(detail, bytes):
        detail = detail.decode("utf-8", errors="replace")
    detail = str(detail)
    detail = re.sub(
        r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",
        "[email redacted]",
        detail,
        flags=re.IGNORECASE,
    )
    detail = re.sub(r"(?i)(password|token|api[_ -]?key)\s*[:=]\s*\S+", r"\1=[redacted]", detail)
    return detail[:240]


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
        logger.warning(
            "Verification email delivery failed: type=%s smtp_code=%s detail=%s",
            type(exc).__name__,
            getattr(exc, "smtp_code", None),
            _smtp_failure_summary(exc),
        )
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
    expiry_note = (
        f"This invitation expires at {expires_at.isoformat()} (UTC). "
        if expires_at
        else ""
    )
    message.set_content(
        f"You have been invited to join the {workspace_name} workspace on Exprofit.\n\n"
        f"Review and accept the invitation here: {invitation_url}\n\n"
        f"{expiry_note}"
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
        logger.warning(
            "Invitation email delivery failed: type=%s smtp_code=%s detail=%s",
            type(exc).__name__,
            getattr(exc, "smtp_code", None),
            _smtp_failure_summary(exc),
        )
        raise EmailDeliveryError("Invitation email could not be sent") from exc
