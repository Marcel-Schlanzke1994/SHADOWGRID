"""Create ignored development configuration without overwriting existing secrets."""

from __future__ import annotations

import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local"
ENV = LOCAL / "development.env"


def main() -> None:
    LOCAL.mkdir(mode=0o700, exist_ok=True)
    if ENV.exists():
        print(f"Existing local configuration preserved: {ENV}")
        return
    values = {
        "APP_ENV": "development",
        "DATABASE_URL": f"sqlite:///{(LOCAL / 'shadowgrid.db').as_posix()}",
        "SECRET_KEY": secrets.token_urlsafe(48),
        "REFRESH_PEPPER": secrets.token_urlsafe(48),
        "SEED_SECRET": secrets.token_urlsafe(32),
        "WEB_ORIGINS": "http://localhost:5173",
        "SMTP_HOST": "localhost",
        "SMTP_PORT": "1025",
        "TRANSLATION_PROVIDER": "disabled",
    }
    ENV.write_text(
        "\n".join(f"{key}={value}" for key, value in values.items()) + "\n", encoding="utf-8"
    )
    print(f"Generated ignored local configuration: {ENV}")


if __name__ == "__main__":
    main()
