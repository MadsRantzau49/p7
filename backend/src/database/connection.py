import os

from dotenv import load_dotenv
from mysql.connector import pooling

load_dotenv()

# https://oneuptime.com/blog/post/2026-03-31-mysql-connection-pooling-python/view
# IMPORTANT
# When a function is done using the connection its important that we close the current connection,
# so it can return to the pool.
database_pool_cfg = pooling.MySQLConnectionPool(
    pool_name="connection_pool",
    pool_size=5,  # Amount of active db connections, which is allowed at once
    host=os.getenv("DATABASE_HOST"),
    port=os.getenv("DATABASE_PORT"),
    database=os.getenv("DATABASE_NAME"),
    user=os.getenv("DATABASE_USER"),
    password=os.getenv("DATABASE_PASSWORD"),
)


def create_db_connection() -> pooling:
    """Create and return a database connection."""
    return database_pool_cfg.get_connection()
