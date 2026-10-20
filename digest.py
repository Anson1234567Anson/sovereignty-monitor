"""Write new tagged records to Markdown, then mark those records as delivered."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from storage import connect

ROOT = Path(__file__).resolve().parent


def escape(text):
    for char in ("\\", "[", "]", "*", "_", "`", "<", ">"):
        text = text.replace(char, "\\" + char)
    return " ".join(text.split())


def write_digest(db, output):
    rows = db.execute("""
        SELECT items.*, item_topics.topic FROM items
        JOIN item_topics ON items.id = item_topics.item_id
        WHERE digested_at IS NULL
        ORDER BY topic, COALESCE(published, '') DESC, id
    """).fetchall()
    grouped = defaultdict(list)
    ids = set()
    for row in rows:
        grouped[row["topic"]].append(row)
        ids.add(row["id"])
    now = datetime.now(timezone.utc).isoformat()
    lines = ["# New sovereignty and privacy items", "", f"Generated: {now}", "",
             f"{len(ids)} new tagged items across {len(grouped)} topics.", ""]
    for topic, items in grouped.items():
        lines.extend([f"## {topic}", ""])
        for item in items:
            url = quote(item["url"], safe=":/?&=%#@+;,$!~*'-._")
            lines.append(f"- [{escape(item['title'])}](<{url}>) — "
                         f"{escape(item['source'])}, {item['published'] or 'date unavailable'}")
            if item["summary"]:
                lines.append(f"  {escape(item['summary'])}")
        lines.append("")
    if not ids:
        lines.extend(["No new tagged items.", ""])
    # Replace atomically before marking delivery; a failed write preserves pending items.
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text("\n".join(lines), encoding="utf-8")
    temporary.replace(output)
    with db:
        db.executemany("UPDATE items SET digested_at = ? WHERE id = ?",
                       [(now, item_id) for item_id in ids])
    return len(ids), len(grouped)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "monitor.sqlite3")
    parser.add_argument("--output", type=Path, default=ROOT / "digest.md")
    args = parser.parse_args()
    db = connect(args.db)
    try:
        items, topics = write_digest(db, args.output)
    finally:
        db.close()
    print(f"DIGEST new_tagged_items={items} topics={topics} output={args.output}")


if __name__ == "__main__":
    main()
