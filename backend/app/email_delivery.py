"""SMTP delivery for account verification messages."""

import smtplib
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
