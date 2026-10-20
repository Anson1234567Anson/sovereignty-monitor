from datetime import timedelta
from pathlib import Path

from models import Item
from storage import save


def test_gdpr_rolling_publication_window(db):
    now = db.execute("SELECT CURRENT_TIMESTAMP AS now").fetchone()["now"]
    cases = [
        ("recent", now - timedelta(days=1), ["GDPR", "privacy"]),
        ("old", now - timedelta(days=8), ["GDPR"]),
        ("future", now + timedelta(days=1), ["GDPR"]),
        ("unknown", None, ["GDPR"]),
        ("other_topic", now - timedelta(days=1), ["privacy"]),
    ]
    for title, published, topics in cases:
        save(db, Item("edpb", title, f"https://example.test/{title}",
                      published.isoformat() if published else None, ""), topics)
    query = Path(__file__).resolve().parents[1] / "queries" / "gdpr_last_7_days.sql"
    rows = db.execute(query.read_text()).fetchall()
    assert [row["title"] for row in rows] == ["recent"]
    assert rows[0]["source"] == "edpb"
