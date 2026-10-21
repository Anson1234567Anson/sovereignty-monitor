"""Apply numbered SQL migrations once, transactionally, using DATABASE_URL."""
import hashlib
from pathlib import Path
import re

from storage import connect

MIGRATIONS = Path(__file__).resolve().parent / "migrations"


def migrate(db, directory=MIGRATIONS):
    migrations = {}
    for path in directory.glob("*.sql"):
        match = re.fullmatch(r"(\d+)_[a-zA-Z0-9_]+\.sql", path.name)
        if not match or int(match[1]) in migrations:
            raise ValueError(f"Invalid or duplicate migration version: {path.name}")
        migrations[int(match[1])] = path
    if not migrations:
        raise ValueError("No SQL migrations found")

    applied = []
    with db.transaction():
        # Transaction-scoped lock serializes concurrent runners, including first setup.
        db.execute("SELECT pg_advisory_xact_lock(734921060)")
        db.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                checksum TEXT NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        versions = {row["version"]: row for row in db.execute(
            "SELECT version, name, checksum FROM schema_migrations").fetchall()}
        for version, path in sorted(migrations.items()):
            contents = path.read_bytes()
            checksum = hashlib.sha256(contents).hexdigest()
            if version in versions:
                if (versions[version]["checksum"] != checksum
                        or versions[version]["name"] != path.name):
                    raise ValueError(f"Applied migration changed: {path.name}")
                continue
            db.execute(contents.decode("utf-8"))
            db.execute("""
                INSERT INTO schema_migrations (version, name, checksum) VALUES (%s, %s, %s)
            """, (version, path.name, checksum))
            applied.append(path.name)
    return applied


def main():
    with connect() as db:
        applied = migrate(db)
    for name in applied:
        print(f"APPLIED {name}")
    print(f"MIGRATE applied={len(applied)} up_to_date=true")


if __name__ == "__main__":
    main()
