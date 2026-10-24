import os
from contextlib import AbstractContextManager

from dotenv import load_dotenv
from psycopg import Connection
from psycopg_pool import ConnectionPool

load_dotenv()

# https://www.psycopg.org/psycopg3/docs/advanced/pool.html
# IMPORTANT
# Use the connection in a with block: "with create_db_connection() as connection:".
# Do not call connection.close(), that closes the connection and the pool loses it.
database_pool = ConnectionPool(
    kwargs={
        "host": os.getenv("DATABASE_HOST"),
        "port": os.getenv("DATABASE_PORT"),
        "dbname": os.getenv("DATABASE_NAME"),
        "user": os.getenv("DATABASE_USER"),
        "password": os.getenv("DATABASE_PASSWORD"),
        "options": "-c TimeZone=UTC",
    },
    min_size=1,
    max_size=5,
    open=True,
)


def create_db_connection() -> AbstractContextManager[Connection]:
    """Borrow a connection from the pool, use it in a with block"""
    return database_pool.connection()
