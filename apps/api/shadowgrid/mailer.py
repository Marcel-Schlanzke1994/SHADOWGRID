from __future__ import annotations

import smtplib
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.orm import Session

from shadowgrid.config import Settings
from shadowgrid.models import EmailOutbox


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
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=5) as smtp:
            smtp.send_message(email)
    except OSError:
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
