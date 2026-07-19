from unittest.mock import patch

from pydantic import SecretStr
from shadowgrid.config import get_settings
from shadowgrid.database import SessionLocal
from shadowgrid.mailer import deliver_email, queue_email


def test_deliver_email_uses_starttls_and_credentials() -> None:
    settings = get_settings().model_copy(
        update={
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_username": "mailer@example.com",
            "smtp_password": SecretStr("smtp-password"),
            "smtp_starttls": True,
        }
    )
    with SessionLocal() as db:
        message = queue_email(db, "player@example.com", "Welcome", "Hello")
        with patch("shadowgrid.mailer.smtplib.SMTP") as smtp_class:
            smtp = smtp_class.return_value.__enter__.return_value

            assert deliver_email(db, message, settings) is True

            smtp.starttls.assert_called_once_with()
            smtp.login.assert_called_once_with("mailer@example.com", "smtp-password")
            smtp.send_message.assert_called_once()

        assert message.status == "sent"
