from digest import write_digest
from models import Item
from storage import connect, save


def test_only_new_tagged_items_grouped_once_per_topic(tmp_path):
    db = connect(":memory:")
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
    db.close()
