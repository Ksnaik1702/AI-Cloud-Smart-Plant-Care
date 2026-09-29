"""Restore a SQLite backup into a new destination without overwriting files."""
import argparse
import sqlite3
from contextlib import closing
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup", type=Path, help="Verified .sqlite3 backup file")
    parser.add_argument("destination", type=Path, help="New destination path (must not exist)")
    args = parser.parse_args()
    if not args.backup.is_file():
        parser.error("backup file does not exist")
    if args.destination.exists():
        parser.error("destination already exists; choose a new path to prevent accidental overwrite")
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with closing(sqlite3.connect(args.backup)) as source, closing(
            sqlite3.connect(args.destination)
        ) as restored:
            source.backup(restored)
            restored.commit()
            result = restored.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise RuntimeError(f"integrity check failed: {result}")
    except Exception:
        args.destination.unlink(missing_ok=True)
        raise
    print(f"Verified restore created: {args.destination}")


if __name__ == "__main__":
    main()
