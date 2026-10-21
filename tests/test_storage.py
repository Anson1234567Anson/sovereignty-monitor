from dataclasses import replace
from datetime import datetime, timedelta, timezone

import psycopg
import pytest

from models import Item
from storage import connect, register_source, save, throttle


def test_dedupe_by_url_or_hash(db):
    item = Item("edpb", "Privacy guidance", "https://example.test/1", None, "New guidance")
    assert save(db, item, ["privacy"])
    assert not save(db, item, ["privacy"])
    # Same URL, changed content: URL deduplication still applies.
    assert not save(db, replace(item, title="Updated guidance"), ["privacy"])
    # Same normalized content, different source, URL and date: content dedupe.
    assert not save(db, replace(item, source="other", url="https://example.test/2",
                                title="PRIVACY   guidance", published="2026-10-20"), ["privacy"])
    assert save(db, replace(item, title="Different guidance", url="https://example.test/3"), [])
    assert db.execute("SELECT COUNT(*) FROM items").fetchone()["count"] == 2
    assert db.execute("SELECT COUNT(*) FROM item_topics").fetchone()["count"] == 1


@pytest.mark.parametrize("value", [None, "", "   "])
def test_database_url_required(monkeypatch, value):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    if value is not None:
        monkeypatch.setenv("DATABASE_URL", value)
    with pytest.raises(RuntimeError, match="Set DATABASE_URL"):
        connect()


@pytest.mark.parametrize("published, expected", [
    (None, None),
    ("2026-10-20", datetime(2026, 10, 20, tzinfo=timezone.utc)),
    ("2026-10-20T09:00:00", datetime(2026, 10, 20, 9, tzinfo=timezone.utc)),
    ("2026-10-20T09:00:00+08:00", datetime(2026, 10, 20, 1, tzinfo=timezone.utc)),
    ("2026-10-20T09:00:00Z", datetime(2026, 10, 20, 9, tzinfo=timezone.utc)),
])
def test_publication_and_fetch_timestamps(db, published, expected):
    # A non-UTC session must not reinterpret date-only feed values as local time.
    db.execute("SET TIME ZONE 'Asia/Hong_Kong'")
    before = datetime.now(timezone.utc)
    save(db, Item("edpb", "Privacy guidance", "https://example.test/1", published, ""), [])
    row = db.execute("SELECT published, fetched_at FROM items").fetchone()
    assert row["published"] == expected
    assert before <= row["fetched_at"] <= datetime.now(timezone.utc)


def test_topics_and_source_relationships(db):
    register_source(db, "edpb", "https://example.test/feed")
    for number in range(2):
        save(db, Item("edpb", f"Guidance {number}", f"https://example.test/{number}", None, ""),
             ["GDPR", "privacy", "GDPR"])
    assert db.execute("SELECT COUNT(*) FROM sources").fetchone()["count"] == 1
    assert db.execute("SELECT url FROM sources").fetchone()["url"] == "https://example.test/feed"
    assert db.execute("SELECT COUNT(*) FROM item_topics").fetchone()["count"] == 4
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        db.execute("INSERT INTO item_topics VALUES (999, 'GDPR')")
    db.execute("DELETE FROM items")
    assert db.execute("SELECT COUNT(*) FROM item_topics").fetchone()["count"] == 0


def test_failed_save_rolls_back_item_source_and_topics(db):
    item = Item("new_source", "Privacy guidance", "https://example.test/1", None, "")
    with pytest.raises(psycopg.errors.CheckViolation):
        save(db, item, ["GDPR", ""])
    for table in ("items", "sources", "item_topics"):
        assert db.execute(psycopg.sql.SQL("SELECT COUNT(*) FROM {}").format(
            psycopg.sql.Identifier(table))).fetchone()["count"] == 0
    assert save(db, item, ["GDPR"])


def test_request_timing_persists_and_upserts(db, monkeypatch):
    prior = datetime.now(timezone.utc) - timedelta(seconds=2)
    db.execute("INSERT INTO host_requests VALUES (%s, %s)", ("https://example.test", prior))
    sleeps = []
    monkeypatch.setattr("storage.time.time", lambda: prior.timestamp() + 2)
    monkeypatch.setattr("storage.time.sleep", sleeps.append)
    throttle(db, "https://example.test", 5)
    assert sleeps == [3]
    rows = db.execute("SELECT requested_at FROM host_requests").fetchall()
    assert len(rows) == 1 and rows[0]["requested_at"] > prior
