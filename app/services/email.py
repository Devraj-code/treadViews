"""Minimal SMTP email service for password-reset links.

In development with no SMTP configured, emails are logged to stdout so the
reset flow can still be exercised end-to-end.
"""
from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, body: str) -> None:
    if not settings.SMTP_HOST:
        logger.warning("SMTP not configured — email to %s suppressed:\n%s", to, body)
        return
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls()
        if settings.SMTP_USER:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM, [to], msg.as_string())


def send_password_reset(to: str, token: str) -> None:
    link = f"{settings.FRONTEND_RESET_URL}?token={token}"
    body = (
        "You requested a password reset for the TradingView AI Assistant.\n\n"
        f"Reset your password using this link (valid 1 hour):\n{link}\n\n"
        "If you did not request this, you can ignore this email."
    )
    send_email(to, "Reset your TradingView AI Assistant password", body)
