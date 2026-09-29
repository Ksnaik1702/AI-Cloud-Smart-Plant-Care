"""Create a consistent, timestamped backup of the local SQLite database."""
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.getenv("DATABASE_PATH", ROOT / "plant_care.db"))
BACKUPS = ROOT / "backups"


def main() -> None:
    if not SOURCE.is_file():
        raise SystemExit(f"Database not found: {SOURCE}")
    BACKUPS.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    target = BACKUPS / f"plant_care-{stamp}.sqlite3"
    with closing(sqlite3.connect(SOURCE)) as source, closing(sqlite3.connect(target)) as backup:
        source.backup(backup)
        backup.commit()
        result = backup.execute("PRAGMA integrity_check").fetchone()[0]
    if result != "ok":
        target.unlink(missing_ok=True)
        raise SystemExit(f"Backup integrity check failed: {result}")
    print(f"Verified backup created: {target}")


if __name__ == "__main__":
    main()
