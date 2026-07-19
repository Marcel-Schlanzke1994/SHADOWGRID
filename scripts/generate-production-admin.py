from __future__ import annotations

import argparse
import os
import secrets
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create local, ignored Railway bootstrap-admin credentials."
    )
    parser.add_argument("--email", required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".local/production-admin.env"),
    )
    args = parser.parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise SystemExit(f"Refusing to overwrite existing credentials: {output}")

    password = secrets.token_urlsafe(32)
    content = (
        f'BOOTSTRAP_ADMIN_EMAIL="{args.email.strip().lower()}"\n'
        f'BOOTSTRAP_ADMIN_PASSWORD="{password}"\n'
    )
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
    print(f"Credentials created at {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
