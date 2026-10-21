import psycopg
import pytest

from migrate import MIGRATIONS, migrate


def test_migrations_repeat_without_changes(empty_db):
    db = empty_db
    assert migrate(db) == ["001_tables.sql", "002_indexes.sql"]
    first = db.execute("SELECT * FROM schema_migrations ORDER BY version").fetchall()
    assert migrate(db) == []
    assert db.execute("SELECT * FROM schema_migrations ORDER BY version").fetchall() == first
    # Also replay SQL itself, proving IF NOT EXISTS works independently of the ledger.
    for path in sorted(MIGRATIONS.glob("*.sql")):
        db.execute(path.read_text())
    assert db.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()["count"] == 2


def test_failed_migration_rolls_back_ddl_and_version(empty_db, tmp_path):
    path = tmp_path / "001_trial.sql"
    path.write_text("CREATE TABLE trial (id INTEGER); SELECT 1 / 0;")
    with pytest.raises(psycopg.errors.DivisionByZero):
        migrate(empty_db, tmp_path)
    assert empty_db.execute("SELECT to_regclass('trial') AS relation").fetchone()["relation"] is None
    assert empty_db.execute("SELECT to_regclass('schema_migrations') AS relation").fetchone()["relation"] is None
    path.write_text("CREATE TABLE IF NOT EXISTS trial (id INTEGER);")
    assert migrate(empty_db, tmp_path) == ["001_trial.sql"]


def test_reject_changed_applied_migration(empty_db, tmp_path):
    path = tmp_path / "001_trial.sql"
    path.write_text("CREATE TABLE IF NOT EXISTS trial (id INTEGER);")
    migrate(empty_db, tmp_path)
    path.write_text("CREATE TABLE IF NOT EXISTS trial (id TEXT);")
    with pytest.raises(ValueError, match="Applied migration changed"):
        migrate(empty_db, tmp_path)


def test_versions_sort_numerically_and_must_be_unique(empty_db, tmp_path):
    (tmp_path / "10_later.sql").write_text("ALTER TABLE trial ADD COLUMN name TEXT;")
    (tmp_path / "2_first.sql").write_text("CREATE TABLE trial (id INTEGER);")
    assert migrate(empty_db, tmp_path) == ["2_first.sql", "10_later.sql"]
    (tmp_path / "02_duplicate.sql").write_text("SELECT 1;")
    with pytest.raises(ValueError, match="duplicate migration version"):
        migrate(empty_db, tmp_path)
