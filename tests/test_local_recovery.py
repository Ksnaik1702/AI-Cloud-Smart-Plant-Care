import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from uuid import uuid4

import pytest
import requests

from scripts import backup_sqlite, restore_sqlite
from sensor_simulator.offline_queue import OfflineReadingQueue


class Response:
    def raise_for_status(self):
        return None


class Session:
    def __init__(self, error=None):
        self.error = error
        self.sent = []

    def post(self, url, json, headers, timeout):
        if self.error:
            raise self.error
        self.sent.append(json)
        return Response()


def test_offline_queue_keeps_failed_reading_then_removes_after_success():
    queue_path = Path(__file__).with_name(f".test_offline_queue_{uuid4().hex}.sqlite3")
    try:
        queue = OfflineReadingQueue("test-device", queue_path)
        reading = {"device_id": "test-device", "soil_moisture": 35}
        queue.enqueue(reading)

        unavailable = Session(requests.ConnectionError("API offline"))
        assert queue.flush(unavailable, "http://example.invalid", {}, limit=2) == 0
        assert queue.pending_count() == 1

        recovered = Session()
        assert queue.flush(recovered, "http://example.invalid", {}, limit=2) == 1
        assert recovered.sent == [reading]
        assert queue.pending_count() == 0
    finally:
        queue_path.unlink(missing_ok=True)


def test_sqlite_backup_and_restore_are_verified_and_do_not_overwrite(monkeypatch):
    test_dir = Path(__file__).parent
    suffix = uuid4().hex
    source = test_dir / f".test_backup_source_{suffix}.sqlite3"
    restored = test_dir / f".test_backup_restored_{suffix}.sqlite3"
    existing_backups = set(test_dir.glob("plant_care-*.sqlite3"))
    try:
        with closing(sqlite3.connect(source)) as db:
            with db:
                db.execute("CREATE TABLE sample (value TEXT)")
                db.execute("INSERT INTO sample VALUES ('preserved')")

        monkeypatch.setattr(backup_sqlite, "SOURCE", source)
        monkeypatch.setattr(backup_sqlite, "BACKUPS", test_dir)
        backup_sqlite.main()
        backup = next(iter(set(test_dir.glob("plant_care-*.sqlite3")) - existing_backups))
        monkeypatch.setattr(sys, "argv", ["restore_sqlite", str(backup), str(restored)])
        restore_sqlite.main()

        with closing(sqlite3.connect(restored)) as db:
            assert db.execute("SELECT value FROM sample").fetchone()[0] == "preserved"

        with pytest.raises(SystemExit):
            restore_sqlite.main()
    finally:
        source.unlink(missing_ok=True)
        restored.unlink(missing_ok=True)
        for backup in set(test_dir.glob("plant_care-*.sqlite3")) - existing_backups:
            backup.unlink(missing_ok=True)

