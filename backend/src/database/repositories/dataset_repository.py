from models.city import City
from psycopg import Connection
from psycopg.rows import class_row, dict_row


class DatasetRepository:
    def __init__(self, connection: Connection):
        self.connection = connection

    def create_dataset(self, name: str, city_id: int) -> int:
        """Create a dataset and return its ID."""
        cursor = self.connection.cursor()

        try:
            cursor.execute(
                "INSERT INTO datasets (name, city_id) VALUES (%s, %s) RETURNING dataset_id",
                (name, city_id),
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

    def get_or_create_city(self, name: str, time_zone: str) -> City:
        """Return the city with this name, creating it with the given time zone if it does not exist."""
        cursor = self.connection.cursor(row_factory=class_row(City))

        try:
            cursor.execute(
                "INSERT INTO cities (name, time_zone) VALUES (%s, %s) ON CONFLICT (name) DO NOTHING",
                (name, time_zone),
            )
            cursor.execute("SELECT city_id, name, time_zone FROM cities WHERE name = %s", (name,))
            city = cursor.fetchone()

            if city is None:
                raise RuntimeError(f"City {name} was not found after insert")
            return city
        except Exception as error:
            print(f"Failed to get or create city: {error}")
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

    def get_trajectories_cities_from_db(self) -> list[City]:
        """Fetch available trajectory cities from the database."""
        cursor = self.connection.cursor(row_factory=class_row(City))

        try:
            cursor.execute("SELECT city_id, name, time_zone FROM cities ORDER BY name")

            return cursor.fetchall()

        except Exception as error:
            print(f"Failed to retrieve cities from database: {error}")
            raise
        finally:
            cursor.close()
