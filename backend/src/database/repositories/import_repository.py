import json

from models.beijing_trajectory import BeijingTrajectory
from models.porto_trajectory import PortoTrajectory
from psycopg import Connection


class ImportRepository:
    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def insert_porto_trajectories(self, trajectories: list[PortoTrajectory]) -> None:
        """Insert Porto trajectories into the database."""
        cursor = self.connection.cursor()

        try:
            values = []

            for trajectory in trajectories:
                values.append(
                    (
                        trajectory.source_id,
                        trajectory.trip_id,
                        trajectory.call_type,
                        trajectory.origin_call,
                        trajectory.origin_stand,
                        trajectory.taxi_id,
                        trajectory.timestamp,
                        trajectory.day_type,
                        trajectory.missing_data,
                        json.dumps(trajectory.polyline),
                    )
                )

            cursor.executemany(
                """INSERT INTO porto_trajectories (
                            source_id,
                            trip_id,
                            call_type,
                            origin_call,
                            origin_stand,
                            taxi_id,
                            timestamp,
                            day_type,
                            missing_data,
                            polyline)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                values,
            )

        except Exception as error:
            print(f"Failed to insert Porto dataset: {error}")
            raise
        finally:
            cursor.close()

    def insert_beijing_dataset(self, trajectories: list[BeijingTrajectory]) -> None:
        """Insert Beijing trajectories into the database."""
        cursor = self.connection.cursor()

        try:
            values = []
            for trajectory in trajectories:
                points = []

                for point in trajectory.points:
                    points.append(
                        {
                            "date_time": point.date_time,
                            "longitude": point.longitude,
                            "latitude": point.latitude,
                        }
                    )

                values.append((trajectory.source_id, trajectory.taxi_id, json.dumps(points)))

            cursor.executemany(
                "INSERT INTO beijing_trajectories (source_id, taxi_id, points) VALUES (%s, %s, %s)",
                values,
            )

        except Exception as error:
            print(f"Failed to insert beijing dataset: {error}")
            raise
        finally:
            cursor.close()

    def retrieve_porto_dataset_batch(self, batch_size: int, last_source_id: str | None) -> dict:
        """Fetch a batch of Porto trajectories from the database."""
        cursor = self.connection.cursor(dictionary=True)

        try:
            if last_source_id is None:
                cursor.execute("SELECT * FROM porto_trajectories LIMIT %s", (batch_size,))

            else:
                cursor.execute(
                    "SELECT * FROM porto_trajectories WHERE source_id > %s ORDER BY source_id LIMIT %s",
                    (last_source_id, batch_size),
                )

            return cursor.fetchall()
        except Exception as error:
            print(f"Failed to retrieve porto datset: {error}")
            raise
        finally:
            cursor.close()

    def retrieve_beijing_data_batch(self, batch_size: int, last_source_id: str | None) -> dict:
        """Fetch a batch of Beijing trajectories from the database."""
        cursor = self.connection.cursor(dictionary=True)

        try:
            if last_source_id is None:
                cursor.execute("SELECT * FROM beijing_trajectories LIMIT %s", (batch_size,))
            else:
                cursor.execute(
                    "SELECT * FROM beijing_trajectories WHERE source_id > %s ORDER BY source_id LIMIT %s",
                    (last_source_id, batch_size),
                )

            return cursor.fetchall()

        except Exception as error:
            print(f"Failed to retrieve beijing data: {error}")
            raise
        finally:
            cursor.close()
