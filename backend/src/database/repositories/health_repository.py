from psycopg_pool import ConnectionPool


class HealthRepository:
    def __init__(self, pool: ConnectionPool):
        self.pool = pool

    def ping(self) -> bool:
        """Return True if a connection can be borrowed and answers SELECT 1 within 2 seconds."""
        try:
            with self.pool.connection(timeout=2) as connection:
                return connection.execute("SELECT 1").fetchone() == (1,)
        except Exception:
            return False
