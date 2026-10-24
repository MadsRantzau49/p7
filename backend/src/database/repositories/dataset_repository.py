from models.dataset import DataSet
from psycopg import Connection
from psycopg.rows import class_row, dict_row


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
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("SELECT EXISTS returned no row")
            (taken,) = row
            return bool(taken)
        except Exception as error:
            print(f"Failed to check dataset name: {error}")
            raise
        finally:
            cursor.close()

    def create_dataset(self, name: str, time_zone: str) -> int:
        """Create a dataset and return its ID."""
        cursor = self.connection.cursor()

        try:
            cursor.execute(
                "INSERT INTO datasets (name, time_zone) VALUES (%s, %s) RETURNING dataset_id",
                (name, time_zone),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("INSERT ... RETURNING returned no row")
            (dataset_id,) = row
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

            if result is None:
                raise ValueError(f"No dataset named {dataset_name}")
            return result["dataset_id"]
        except Exception as error:
            print(f"Failed to get dataset id: {error}")
            raise
        finally:
            cursor.close()

    def get_trajectories_cities_from_db(self) -> list[DataSet]:
        """Fetch available trajectory cities from the database."""
        cursor = self.connection.cursor(row_factory=class_row(DataSet))

        try:
            cursor.execute("SELECT * FROM datasets ORDER BY name")

            return cursor.fetchall()

        except Exception as error:
            print(f"Failed to retrieve cities from database: {error}")
            raise
        finally:
            cursor.close()
