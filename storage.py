"""Postgres persistence, content/URL deduplication and digest delivery state."""
import hashlib
import os
import time
from datetime import datetime, timezone

import psycopg
from psycopg.rows import dict_row

from tagger import normalize


def connect():
    """Use only DATABASE_URL; never fall back to a local or embedded database."""
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("Set DATABASE_URL before running the monitor")
    db = psycopg.connect(url, autocommit=True, row_factory=dict_row)
    db.execute("SET TIME ZONE 'UTC'")
    return db


def register_source(db, source_id, url=None):
    db.execute("""
        INSERT INTO sources (id, url) VALUES (%s, %s)
        ON CONFLICT (id) DO UPDATE SET url = COALESCE(EXCLUDED.url, sources.url)
    """, (source_id, url))


def publication_time(value):
    """Treat date-only and timezone-free parser values as UTC, independent of host."""
    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def save(db, item, topics):
    # Exclude source/URL/date so syndicated copies with the same text dedupe.
    content = normalize(item.title) + "\n" + normalize(item.summary)
    digest = hashlib.sha256(content.encode()).hexdigest()
    published = publication_time(item.published)
    with db.transaction():
        db.execute("INSERT INTO sources (id) VALUES (%s) ON CONFLICT DO NOTHING",
                   (item.source,))
        row = db.execute("""
            INSERT INTO items (source_id, title, url, published, summary, content_hash)
            VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING
            RETURNING id
        """, (item.source, item.title, item.url, published, item.summary, digest)).fetchone()
        if row is None:
            return False
        with db.cursor() as cursor:
            cursor.executemany("""
                INSERT INTO item_topics (item_id, topic) VALUES (%s, %s)
                ON CONFLICT DO NOTHING
            """, [(row["id"], topic) for topic in set(topics)])
    return True


def throttle(db, origin, delay):
    """Persist request starts so consecutive CLI invocations also observe delays."""
    row = db.execute("SELECT requested_at FROM host_requests WHERE origin = %s",
                     (origin,)).fetchone()
    if row:
        time.sleep(max(0, row["requested_at"].timestamp() + delay - time.time()))
    db.execute("""
        INSERT INTO host_requests (origin, requested_at) VALUES (%s, %s)
        ON CONFLICT (origin) DO UPDATE SET requested_at = EXCLUDED.requested_at
    """, (origin, datetime.now(timezone.utc)))
