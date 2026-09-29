import json
from datetime import datetime, time

from models.beijing_trajectory import BeijingTrajectory
from models.dataset import DataSet
from models.porto_trajectory import PortoTrajectory
from models.uniformed_trajectories import UniformedTrajectories


def get_dataset_id(context, dataset_name: str) -> int:
    """Get the ID of a dataset by its name."""
    cursor = context.cursor(dictionary=True)

    try:
        cursor.execute("SELECT dataset_id FROM datasets WHERE name = %s", (dataset_name,))
        result = cursor.fetchone()

        return result["dataset_id"]
    except Exception as error:
        print(f"Failed to get dataset id: {error}")
        raise
    finally:
        cursor.close()


def create_source_trajectories(context, dataset_id: int, source_ids: list[str]) -> None:
    """Create source trajectory entries for a dataset."""
    cursor = context.cursor()

    try:
        values = []

        for source_id in source_ids:
            values.append((source_id, dataset_id))

        cursor.executemany("INSERT INTO source_trajectories (source_id, dataset_id) VALUES (%s, %s)", values)

    except Exception as error:
        print(f"Failed to create source trajectory: {error}")
        raise

    finally:
        cursor.close()


def insert_porto_trajectories(context, trajectories: list[PortoTrajectory]) -> None:
    """Insert Porto trajectories into the database."""
    cursor = context.cursor()

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


def insert_beijing_dataset(context, trajectories: list[BeijingTrajectory]) -> None:
    """Insert Beijing trajectories into the database."""
    cursor = context.cursor()

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


def retrieve_porto_dataset_batch(context, batch_size: int, last_source_id: str | None) -> dict:
    """Fetch a batch of Porto trajectories from the database."""
    cursor = context.cursor(dictionary=True)

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


def retrieve_beijing_data_batch(context, batch_size: int, last_source_id: str | None) -> dict:
    """Fetch a batch of Beijing trajectories from the database."""
    cursor = context.cursor(dictionary=True)

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


def insert_data_uniformed_trajectories(context, trajectories: list[UniformedTrajectories]) -> None:
    """Insert uniformed trajectories into the database."""
    vehicle_type_ids = get_vehicle_type_ids(context)
    cursor = context.cursor()

    try:
        values = []
        for trajectory in trajectories:
            points = []

            for point in trajectory.points:
                points.append(
                    {
                        "longitude": point.longitude,
                        "latitude": point.latitude,
                        "point_timestamp": point.point_timestamp.isoformat(),
                    }
                )

            values.append(
                (
                    trajectory.vehicle_id,
                    vehicle_type_ids[trajectory.vehicle_type],
                    trajectory.trajectory_date,
                    trajectory.city,
                    json.dumps(points),
                    trajectory.source_id,
                )
            )

        cursor.executemany(
            (
                "INSERT INTO uniformed_trajectories "
                "(vehicle_id, vehicle_type_id, trajectory_date, city, points, source_id) "
                "VALUES (%s, %s, %s, %s, %s, %s)"
            ),
            values,
        )

    except Exception:
        print("Failed to insert data to uniformed schema")
        raise
    finally:
        cursor.close()


async def get_trajectories_from_db(
    context,
    city: str,
    start_date: datetime | None,
    end_date: datetime | None,
    start_time: time | None,
    end_time: time | None,
    limit: int | None,
) -> list[UniformedTrajectories]:
    """Fetch trajectories for a city, with only the points inside the date range and time window.
    Trips are first picked by city, date, and whether their start and end times can
    overlap the time window. Their points are then filtered in the database, and the
    rows are grouped back into one dict per trajectory.
    """

    cursor = context.cursor(dictionary=True)

    try:
        # Get the end time of the trajectory
        trajectory_end = "CAST(JSON_UNQUOTE(JSON_EXTRACT(points, '$[last].point_timestamp')) AS DATETIME)"

        # conditions for the trajectories, the city,
        # and it started before the window ends and ended after the window starts
        conditions = [
            "city = %s",
            f"(DATE({trajectory_end}) <> DATE(trajectory_date)"
            f" OR (TIME(trajectory_date) <= %s AND TIME({trajectory_end}) >= %s))",
        ]

        values: list = [city, end_time, start_time]

        if start_date is not None:
            conditions.append("trajectory_date >= %s")
            values.append(start_date)

        if end_date is not None:
            conditions.append("trajectory_date < %s")
            values.append(end_date)

        trip_limit = ""
        if limit is not None:
            trip_limit = "LIMIT %s"
            values.append(limit)

        point_conditions = ["TIME(jt.point_timestamp) BETWEEN %s AND %s"]
        point_values: list = [start_time, end_time]

        # Trips starting before end_date can still have points after it
        if end_date is not None:
            point_conditions.append("jt.point_timestamp < %s")
            point_values.append(end_date)

        sql = f"""
            SELECT t.trajectory_id, t.vehicle_id, vt.name AS vehicle_type,
                   t.trajectory_date, t.city, t.source_id,
                   jt.latitude, jt.longitude, jt.point_timestamp
            FROM (
                SELECT trajectory_id
                FROM uniformed_trajectories
                WHERE {" AND ".join(conditions)}
                ORDER BY trajectory_date, trajectory_id
                {trip_limit}
            ) AS ids
            JOIN uniformed_trajectories AS t
                ON t.trajectory_id = ids.trajectory_id
            JOIN JSON_TABLE(t.points, '$[*]' COLUMNS (
                idx FOR ORDINALITY,
                latitude DOUBLE PATH '$.latitude',
                longitude DOUBLE PATH '$.longitude',
                point_timestamp DATETIME PATH '$.point_timestamp')) AS jt
            LEFT JOIN vehicle_types AS vt
                ON t.vehicle_type_id = vt.vehicle_type_id
            WHERE {" AND ".join(point_conditions)}
            ORDER BY t.trajectory_date, t.trajectory_id, jt.idx
            """

        cursor.execute(sql, values + point_values)

        result = []
        current = None

        for row in cursor.fetchall():
            if current is None or current["trajectory_id"] != row["trajectory_id"]:
                current = {
                    "trajectory_id": row["trajectory_id"],
                    "vehicle_id": row["vehicle_id"],
                    "vehicle_type": row["vehicle_type"],
                    "trajectory_date": row["trajectory_date"],
                    "city": row["city"],
                    "source_id": row["source_id"],
                    "points": [],
                }
                result.append(current)

            current["points"].append(
                {
                    "latitude": row["latitude"],
                    "longitude": row["longitude"],
                    "point_timestamp": row["point_timestamp"].isoformat(),
                }
            )

        return result

    except Exception as error:
        print(f"Failed to get trajectories from database: {error}")
        raise
    finally:
        cursor.close()


def dataset_name_taken(context, name: str) -> bool:
    """Check if a dataset or city already uses the given name."""
    cursor = context.cursor()

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


def create_dataset(context, name: str) -> int:
    """Create a dataset and return its ID."""
    cursor = context.cursor()

    try:
        cursor.execute("INSERT INTO datasets (name) VALUES (%s)", (name,))
        return cursor.lastrowid

    except Exception as error:
        print(f"Failed to create dataset: {error}")
        raise
    finally:
        cursor.close()


async def get_trajectories_cities_from_db(context) -> list[DataSet]:
    """Fetch available trajectory cities from the database."""
    cursor = context.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM datasets ORDER BY name")

        return cursor.fetchall()

    except Exception as error:
        print(f"Failed to retrieve cities from database: {error}")
        raise
    finally:
        cursor.close()


def get_vehicle_type_ids(context) -> dict[str, int]:
    """Fetch vehicle type IDs from the database."""
    cursor = context.cursor()

    try:
        cursor.execute("SELECT name, vehicle_type_id FROM vehicle_types")
        return dict(cursor.fetchall())
    except Exception as error:
        print(f"Failed to retrieve vehicle types from database: {error}")
        raise
    finally:
        cursor.close()
