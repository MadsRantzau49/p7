from database.connection import create_db_connection


def test_create_db_connection():
    """Check a pooled connection reaches PostgreSQL with MobilityDB."""
    with create_db_connection() as connection:
        row = connection.execute("SELECT mobilitydb_version()").fetchone()

    assert row is not None
    (mobilitydb_version,) = row
    assert mobilitydb_version.startswith("MobilityDB")
