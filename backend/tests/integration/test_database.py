from database.connection import create_db_connection
from mysql.connector import pooling


def test_create_db_connection():
    """Test that a database connection can be created."""
    connection = create_db_connection()

    try:
        assert connection is not None
        assert isinstance(connection, pooling.PooledMySQLConnection)
        assert connection.is_connected()
    finally:
        connection.close()
