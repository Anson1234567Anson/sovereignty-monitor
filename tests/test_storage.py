from dataclasses import replace

from models import Item
from storage import connect, save


def test_dedupe_by_url_or_hash():
    db = connect(":memory:")
    item = Item("edpb", "Privacy guidance", "https://example.test/1", None, "New guidance")
    assert save(db, item, ["privacy"])
    assert not save(db, item, ["privacy"])
    # Same URL, changed content: URL deduplication still applies.
    assert not save(db, replace(item, title="Updated guidance"), ["privacy"])
    # Same normalized content, different source, URL and date: content dedupe.
    assert not save(db, replace(item, source="other", url="https://example.test/2",
                                title="PRIVACY   guidance", published="2026-10-20"), ["privacy"])
    assert save(db, replace(item, title="Different guidance", url="https://example.test/3"), [])
    assert db.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 2
    assert db.execute("SELECT COUNT(*) FROM item_topics").fetchone()[0] == 1
    db.close()
