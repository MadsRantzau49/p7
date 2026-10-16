from mysql.connector.pooling import PooledMySQLConnection


class DatabaseActions:
    def __init__(self, connection: PooledMySQLConnection):
        self.connection = connection

    def commit(self):
        """Commit changes to the database"""
        self.connection.commit()

    def rollback(self):
        """Rolls back changes, if a write to the database failed"""
        self.connection.rollback()
