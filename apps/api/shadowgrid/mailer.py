from __future__ import annotations

import smtplib
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from shadowgrid.config import Settings
from shadowgrid.models import EmailOutbox


def account_email_copy(
    kind: Literal["verify_email", "password_reset"],
    locale: str,
    link: str,
) -> tuple[str, str]:
    german = locale.lower().startswith("de")
    if kind == "verify_email":
        if german:
            return (
                "Bestätige dein SHADOWGRID-Konto",
                "Willkommen bei SHADOWGRID. Bestätige dein Konto:\n"
                f"{link}\n\n"
                "Dieses fiktive Spiel fragt nie nach realen operativen Informationen.",
            )
        return (
            "Verify your SHADOWGRID account",
            "Welcome to SHADOWGRID. Verify your account:\n"
            f"{link}\n\n"
            "This fictional game never requests real-world operational information.",
        )
    if german:
        return (
            "Setze dein SHADOWGRID-Passwort zurück",
            f"Setze dein Passwort zurück:\n{link}\n\n"
            "Wenn du dies nicht angefordert hast, ignoriere diese Nachricht.",
        )
    return (
        "Reset your SHADOWGRID password",
        f"Reset your password:\n{link}\n\nIf you did not request this, ignore this message.",
    )


def queue_email(db: Session, recipient: str, subject: str, body: str) -> EmailOutbox:
    message = EmailOutbox(recipient=recipient, subject=subject, body=body)
    db.add(message)
    db.flush()
    return message


def deliver_email(db: Session, message: EmailOutbox, settings: Settings) -> bool:
    email = EmailMessage()
    email["From"] = settings.smtp_from
    email["To"] = message.recipient
    email["Subject"] = message.subject
    email.set_content(message.body)
    message.attempts += 1
    smtp_class = smtplib.SMTP_SSL if settings.smtp_use_ssl else smtplib.SMTP
    try:
        with smtp_class(settings.smtp_host, settings.smtp_port, timeout=5) as smtp:
            if settings.smtp_starttls:
                smtp.starttls()
            if settings.smtp_username is not None and settings.smtp_password is not None:
                smtp.login(
                    settings.smtp_username,
                    settings.smtp_password.get_secret_value(),
                )
            smtp.send_message(email)
    except (OSError, smtplib.SMTPException):
        message.status = "retry"
        message.next_attempt_at = datetime.now(UTC) + timedelta(
            minutes=min(60, 2**message.attempts)
        )
        return False
    message.status = "sent"
    message.sent_at = datetime.now(UTC)
    return True


def deliver_pending_email(db: Session, settings: Settings, limit: int = 50) -> int:
    now = datetime.now(UTC)
    messages = db.scalars(
        select(EmailOutbox)
        .where(EmailOutbox.status.in_(("pending", "retry")), EmailOutbox.next_attempt_at <= now)
        .order_by(EmailOutbox.created_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    sent = sum(1 for message in messages if deliver_email(db, message, settings))
    db.commit()
    return sent
