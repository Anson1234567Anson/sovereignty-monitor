"""Database tests require a real Postgres via DATABASE_URL, never SQLite/mocks."""
from uuid import uuid4

from psycopg import sql
import pytest

from migrate import migrate
from storage import connect


@pytest.fixture
def empty_db():
    # Each test gets a private schema; public data is never truncated or dropped.
    with connect() as connection:
        schema = sql.Identifier("monitor_test_" + uuid4().hex)
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(schema))
        try:
            connection.execute(sql.SQL("SET search_path TO {}").format(schema))
            yield connection
        finally:
            connection.execute("SET search_path TO public")
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(schema))


@pytest.fixture
def db(empty_db):
    migrate(empty_db)
    return empty_db
