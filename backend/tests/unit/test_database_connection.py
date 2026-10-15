"""Lazy initialization allows the frontend's CSV workflow without a database."""

from unittest.mock import Mock

from database import connection


def test_database_pool_is_created_once_on_first_use(monkeypatch):
    """The first DB request initializes one pool; subsequent requests reuse it."""
    factory = Mock()
    monkeypatch.setattr(connection, "_database_pool", None)
    monkeypatch.setattr(connection.pooling, "MySQLConnectionPool", factory)
    first = connection.create_db_connection()
    second = connection.create_db_connection()
    factory.assert_called_once()
    assert factory.return_value.get_connection.call_count == 2
    assert first is second
