import pytest

from digest import write_digest
from models import Item
from storage import save


def test_only_new_tagged_items_grouped_once_per_topic(db, tmp_path):
    save(db, Item("edpb", "GDPR privacy", "https://example.test/privacy", None, "Guidance"),
         ["GDPR", "privacy"])
    save(db, Item("eurlex", "Wheat", "https://example.test/wheat", None, "Quotas"), [])
    output = tmp_path / "digest.md"
    assert write_digest(db, output) == (1, 2)
    content = output.read_text()
    assert "## GDPR" in content and "## privacy" in content
    assert "[GDPR privacy](<https://example.test/privacy>)" in content
    assert "Wheat" not in content
    assert write_digest(db, output) == (0, 0)
    assert "No new tagged items." in output.read_text()


def test_output_failure_preserves_pending_items(db, tmp_path):
    save(db, Item("edpb", "GDPR", "https://example.test/1", "2026-10-20", ""), ["GDPR"])
    with pytest.raises(OSError):
        write_digest(db, tmp_path / "missing_directory" / "digest.md")
    assert db.execute("SELECT digested_at FROM items").fetchone()["digested_at"] is None
    assert write_digest(db, tmp_path / "digest.md") == (1, 1)
    assert "2026-10-20" in (tmp_path / "digest.md").read_text()
    assert db.execute("SELECT digested_at FROM items").fetchone()["digested_at"] is not None
