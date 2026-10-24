from models.dataset import DataSet
from psycopg import Connection, cursor
from psycopg.rows import dict_row

class DatasetRepository:
    def __init__(self, connection: Connection):
        self.connection = connection

    def dataset_name_taken(self, name: str) -> bool:
        """Check if a dataset or city already uses the given name."""
        cursor = self.connection.cursor()

        try:
            cursor.execute(
                "SELECT EXISTS(SELECT 1 FROM datasets WHERE name = %s) "
                "OR EXISTS(SELECT 1 FROM uniformed_trajectories WHERE city = %s)",
                (name, name),
            )
            (taken,) = cursor.fetchone()
            return bool(taken)
        except Exception as error:
            print(f"Failed to check dataset name: {error}")
            raise
        finally:
            cursor.close()

    def create_dateset(self, name: str, time_zone: str) -> int:
        """Create a dataset and return its ID."""
        cursor = self.connection.cursor()

        try:
            cursor.execute(
                "INSERT INTO datasets (name, time_zone) VALUES (%s, %s) RETURNING dataset_id",
                (name, time_zone),
            )
            (dataset_id,) = cursor.fetchone()
            return dataset_id
        except Exception as error:
            print(f"Failed to create dataset: {error}")
            raise
        finally:
            cursor.close()

    def get_dataset_id(self, dataset_name: str) -> int:
        """Get the ID of a dataset by its name."""
        cursor = self.connection.cursor(row_factory=dict_row)

        try:
            cursor.execute("SELECT dataset_id FROM datasets WHERE name = %s", (dataset_name,))
            result = cursor.fetchone()

            return result["dataset_id"]
        except Exception as error:
            print(f"Failed to get dataset id: {error}")
            raise
        finally:
            cursor.close()

    def get_trajectories_cities_from_db(self) -> list[DataSet]:
        """Fetch available trajectory cities from the database."""
        cursor = self.connection.cursor(row_factory=dict_row)

        try:
            cursor.execute("SELECT * FROM datasets ORDER BY name")

            return cursor.fetchall()

        except Exception as error:
            print(f"Failed to retrieve cities from database: {error}")
            raise
        finally:
            cursor.close()
