from unittest.mock import patch

from pydantic import SecretStr
from shadowgrid.config import get_settings
from shadowgrid.database import SessionLocal
from shadowgrid.mailer import account_email_copy, deliver_email, queue_email


def test_account_email_copy_is_complete_in_german_and_english() -> None:
    verification_url = "https://play.shadowgrid.example/verify-email?token=test"
    reset_url = "https://play.shadowgrid.example/reset-password?token=test"

    english_subject, english_body = account_email_copy("verify_email", "en", verification_url)
    german_subject, german_body = account_email_copy("verify_email", "de-DE", verification_url)
    assert english_subject == "Verify your SHADOWGRID account"
    assert "Welcome to SHADOWGRID" in english_body
    assert german_subject == "Bestätige dein SHADOWGRID-Konto"
    assert "Willkommen bei SHADOWGRID" in german_body
    assert verification_url in english_body and verification_url in german_body

    english_reset_subject, english_reset_body = account_email_copy(
        "password_reset", "en-US", reset_url
    )
    german_reset_subject, german_reset_body = account_email_copy("password_reset", "de", reset_url)
    assert english_reset_subject == "Reset your SHADOWGRID password"
    assert "If you did not request this" in english_reset_body
    assert german_reset_subject == "Setze dein SHADOWGRID-Passwort zurück"
    assert "Wenn du dies nicht angefordert hast" in german_reset_body
    assert reset_url in english_reset_body and reset_url in german_reset_body


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
