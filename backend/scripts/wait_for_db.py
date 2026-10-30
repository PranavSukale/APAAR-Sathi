from __future__ import annotations

import sys
import time

from sqlalchemy import text

from backend.app.core.db import owner_engine


def main() -> int:
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            with owner_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
            print("database ready")
            return 0
        except Exception as exc:  # noqa: BLE001
            print(f"waiting for db... ({exc.__class__.__name__})")
            time.sleep(2)
    print("database not ready in time", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
