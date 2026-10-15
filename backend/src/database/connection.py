import os
from threading import Lock

from dotenv import load_dotenv
from mysql.connector import pooling

load_dotenv()

# https://oneuptime.com/blog/post/2026-03-31-mysql-connection-pooling-python/view
# IMPORTANT
# When a function is done using the connection its important that we close the current connection,
# so it can return to the pool.
_database_pool: pooling.MySQLConnectionPool | None = None
_pool_lock = Lock()


def create_db_connection() -> pooling.PooledMySQLConnection:
    """Initialize the shared pool on first database use, then return a connection.

    The CSV preview and in-memory pathlet API can start without a database.
    Serialize initialization because synchronous endpoints use worker threads.
    """
    global _database_pool
    with _pool_lock:
        if _database_pool is None:
            _database_pool = pooling.MySQLConnectionPool(
                pool_name="connection_pool",
                pool_size=5,
                host=os.getenv("DATABASE_HOST"),
                port=os.getenv("DATABASE_PORT"),
                database=os.getenv("DATABASE_NAME"),
                user=os.getenv("DATABASE_USER"),
                password=os.getenv("DATABASE_PASSWORD"),
            )
        pool = _database_pool
    return pool.get_connection()
