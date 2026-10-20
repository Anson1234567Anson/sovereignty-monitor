"""SQLite persistence, content/URL deduplication and digest delivery state."""
import hashlib
import sqlite3
import time

from tagger import normalize


def connect(path):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY,
            source TEXT NOT NULL, title TEXT NOT NULL, url TEXT NOT NULL UNIQUE,
            published TEXT, summary TEXT NOT NULL, hash TEXT NOT NULL UNIQUE,
            digested_at TEXT
        );
        CREATE TABLE IF NOT EXISTS item_topics (
            item_id INTEGER NOT NULL REFERENCES items(id), topic TEXT NOT NULL,
            PRIMARY KEY (item_id, topic)
        );
        CREATE TABLE IF NOT EXISTS host_requests (
            origin TEXT PRIMARY KEY, requested_at REAL NOT NULL
        );
    """)
    db.execute("PRAGMA foreign_keys = ON")
    return db


def save(db, item, topics):
    # Exclude source/URL/date so syndicated copies with the same text dedupe.
    content = normalize(item.title) + "\n" + normalize(item.summary)
    digest = hashlib.sha256(content.encode()).hexdigest()
    with db:
        cursor = db.execute("""
            INSERT INTO items (source, title, url, published, summary, hash)
            VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT DO NOTHING
        """, (item.source, item.title, item.url, item.published, item.summary, digest))
        if not cursor.rowcount:
            return False
        db.executemany("INSERT INTO item_topics VALUES (?, ?)",
                       [(cursor.lastrowid, topic) for topic in set(topics)])
    return True


def throttle(db, origin, delay):
    """Persist request starts so consecutive CLI invocations also observe delays."""
    row = db.execute("SELECT requested_at FROM host_requests WHERE origin = ?",
                     (origin,)).fetchone()
    if row:
        time.sleep(max(0, row[0] + delay - time.time()))
    with db:
        db.execute("INSERT OR REPLACE INTO host_requests VALUES (?, ?)",
                   (origin, time.time()))
