"""Durable SQLite spool for readings waiting to reach the local API."""
import hashlib
import json
import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import requests


class OfflineReadingQueue:
    def __init__(self, device_id: str, database_path: Path | None = None):
        key = hashlib.sha256(device_id.encode("utf-8")).hexdigest()[:16]
        self.path = Path(database_path) if database_path else Path(__file__).with_name(
            f"pending_readings_{key}.sqlite3"
        )
        with self._connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS pending_readings ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, payload TEXT NOT NULL)"
            )

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.execute("PRAGMA synchronous=FULL")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def enqueue(self, payload: dict) -> None:
        encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        with self._connect() as db:
            db.execute("INSERT INTO pending_readings(payload) VALUES(?)", (encoded,))

    def pending_count(self) -> int:
        with self._connect() as db:
            return db.execute("SELECT COUNT(*) FROM pending_readings").fetchone()[0]

    def flush(self, session: requests.Session, api_url: str, headers: dict,
              limit: int = 20) -> int:
        sent = 0
        while sent < limit:
            with self._connect() as db:
                row = db.execute(
                    "SELECT id,payload FROM pending_readings ORDER BY id LIMIT 1"
                ).fetchone()
            if row is None:
                break
            try:
                response = session.post(
                    api_url, json=json.loads(row[1]), headers=headers, timeout=5
                )
                response.raise_for_status()
            except (requests.RequestException, ValueError) as exc:
                logging.warning("Could not send queued reading; keeping it for retry: %s", exc)
                return sent
            with self._connect() as db:
                db.execute("DELETE FROM pending_readings WHERE id=?", (row[0],))
            sent += 1
        return sent
