from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = PROJECT_ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from shadowgrid.main import app  # noqa: E402


def main() -> None:
    target = PROJECT_ROOT / ".local" / "openapi.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Exported {target}")


if __name__ == "__main__":
    main()
