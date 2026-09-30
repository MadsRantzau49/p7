import json
from datetime import date, time, timedelta

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
    start_date: date | None,
    end_date: date | None,
    start_time: time | None,
    end_time: time | None,
    limit: int | None,
) -> list[UniformedTrajectories]:
    """Fetch trajectories that lie completely inside the date range and daily time window.

    A trajectory is only returned if all its points are inside the period: it must
    start on or after start_date and end on or before end_date, and on every day its first
    and last point must be inside the time window. Trajectories that are partly
    outside are left out entirely.

    The time window applies to every day in the date range. If start_time is later
    than end_time, the window crosses midnight (e.g. 23:50-02:00), and trips that
    run from the evening into the next morning are included.

    Missing dates or times mean no limit on that side.
    """

    cursor = context.cursor(dictionary=True)

    try:
        # Get the last time stamp of a trajectory
        trajectory_end = "CAST(JSON_UNQUOTE(JSON_EXTRACT(points, '$[last].point_timestamp')) AS DATETIME)"

        conditions = [
            "city = %s",
        ]

        values: list = [city]

        if start_date is not None:
            conditions.append("trajectory_date >= %s")
            values.append(start_date)

        if end_date is not None:
            day_after_end = end_date + timedelta(days=1)
            conditions.append("t.trajectory_date < %s")
            values.append(day_after_end)
            conditions.append(f"{trajectory_end} < %s")
            values.append(day_after_end)

        if start_time is not None and end_time is not None and start_time > end_time:
            # Overnight window, e.g. 23:50-02:00
            conditions.append(
                f"((DATEDIFF({trajectory_end}, t.trajectory_date) = 0"
                f" AND (TIME(t.trajectory_date) >= %s OR TIME({trajectory_end}) <= %s))"
                f" OR (DATEDIFF({trajectory_end}, t.trajectory_date) = 1"
                f" AND TIME(t.trajectory_date) >= %s AND TIME({trajectory_end}) <= %s))"
            )
            values.extend([start_time, end_time, start_time, end_time])

        else:
            # Normal window, e.g. 14:45-15:00
            if start_time is not None or end_time is not None:
                conditions.append(f"DATEDIFF({trajectory_end}, t.trajectory_date) = 0")

            if start_time is not None:
                conditions.append("TIME(t.trajectory_date) >= %s")
                values.append(start_time)

            if end_time is not None:
                conditions.append(f"TIME({trajectory_end}) <= %s")
                values.append(end_time)

        sql = f"""
            SELECT t.trajectory_id, t.vehicle_id, vt.name AS vehicle_type,
                   t.trajectory_date, t.city, t.points, t.source_id
            FROM uniformed_trajectories AS t
            LEFT JOIN vehicle_types AS vt
                ON t.vehicle_type_id = vt.vehicle_type_id
            WHERE {" AND ".join(conditions)}
            ORDER BY t.trajectory_date, t.trajectory_id
            """

        if limit is not None:
            sql += " LIMIT %s"
            values.append(limit)

        cursor.execute(sql, values)

        trajectories = cursor.fetchall()

        for trajectory in trajectories:
            trajectory["points"] = json.loads(trajectory["points"])

        return trajectories

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
