from datetime import date, datetime, time, timedelta
from typing import Any

from helpers.time_helper import to_utc_iso
from models.bounding_box import BoundingBox
from models.trajectory_segments import TrajectorySegments
from models.uniformed_trajectories import UniformedTrajectories, UniformedTrajectoryPoint
from models.upload_row import VehicleType
from psycopg import Connection, sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


class TrajectoryRepository:
    def __init__(self, connection: Connection):
        self.connection = connection

    async def get_trajectories_from_db(
        self,
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
        cursor = self.connection.cursor(row_factory=dict_row)

        try:
            conditions = [sql.SQL("t.city = %(city)s")]
            values: dict[str, str | date | time | int | None] = {"city": city, "limit": limit}

            if start_date is not None:
                conditions.append(
                    sql.SQL("t.trajectory_date >= (%(start_date)s::timestamp AT TIME ZONE z.time_zone)")
                )
                values["start_date"] = start_date

            if end_date is not None:
                conditions.append(
                    sql.SQL("t.trajectory_date < (%(day_after_end)s::timestamp AT TIME ZONE z.time_zone)")
                )
                conditions.append(sql.SQL("l.local_end < %(day_after_end)s"))
                values["day_after_end"] = end_date + timedelta(days=1)

            if start_time is not None and end_time is not None and start_time > end_time:
                # Overnight window, e.g. 23:50-02:00
                conditions.append(
                    sql.SQL(
                        "((l.local_end::date = l.local_start::date"
                        " AND (l.local_start::time >= %(start_time)s OR l.local_end::time <= %(end_time)s))"
                        " OR (l.local_end::date = l.local_start::date + 1"
                        " AND l.local_start::time >= %(start_time)s AND l.local_end::time <= %(end_time)s))"
                    )
                )
                values["start_time"] = start_time
                values["end_time"] = end_time

            else:
                # Normal window, e.g. 14:45-15:00
                if start_time is not None or end_time is not None:
                    conditions.append(sql.SQL("l.local_end::date = l.local_start::date"))

                if start_time is not None:
                    conditions.append(sql.SQL("l.local_start::time >= %(start_time)s"))
                    values["start_time"] = start_time

                if end_time is not None:
                    conditions.append(sql.SQL("l.local_end::time <= %(end_time)s"))
                    values["end_time"] = end_time

            query = sql.SQL("""
                            WITH z AS (SELECT time_zone
                                       FROM cities
                                       WHERE name = %(city)s)
                            SELECT t.trajectory_id,
                                   t.vehicle_id,
                                   vt.name AS vehicle_type,
                                   t.trajectory_date,
                                   t.city,
                                   t.points,
                                   t.source_id
                            FROM uniformed_trajectories AS t
                                     CROSS JOIN z
                                     CROSS JOIN LATERAL (
                                SELECT t.trajectory_date AT TIME ZONE z.time_zone AS local_start,
                                    (t.points -> -1 ->> 'point_timestamp') ::timestamptz
                                    AT TIME ZONE z.time_zone AS local_end
                                ) AS l
                                     LEFT JOIN vehicle_types AS vt
                                               ON t.vehicle_type_id = vt.vehicle_type_id
                            WHERE {conditions}
                            ORDER BY t.trajectory_date, t.trajectory_id
                            LIMIT %(limit)s
                            """).format(conditions=sql.SQL(" AND ").join(conditions))

            cursor.execute(query, values)

            return [
                UniformedTrajectories(
                    trajectory_id=trajectory["trajectory_id"],
                    vehicle_id=trajectory["vehicle_id"],
                    vehicle_type=VehicleType(trajectory["vehicle_type"]),
                    trajectory_date=trajectory["trajectory_date"],
                    city=trajectory["city"],
                    points=[
                        UniformedTrajectoryPoint(
                            longitude=point["longitude"],
                            latitude=point["latitude"],
                            point_timestamp=datetime.fromisoformat(point["point_timestamp"]),
                        )
                        for point in trajectory["points"]
                    ],
                    source_id=trajectory["source_id"],
                )
                for trajectory in cursor.fetchall()
            ]

        except Exception as error:
            print(f"Failed to get trajectories from database: {error}")
            raise
        finally:
            cursor.close()

    def create_source_trajectories(self, dataset_id: int, source_ids: list[str]) -> None:
        """Create source trajectory entries for a dataset."""
        cursor = self.connection.cursor()

        try:
            values = []

            for source_id in source_ids:
                values.append((source_id, dataset_id))

            cursor.executemany(
                "INSERT INTO source_trajectories (source_id, dataset_id) VALUES (%s, %s)", values
            )

        except Exception as error:
            print(f"Failed to create source trajectory: {error}")
            raise

        finally:
            cursor.close()

    def retrieve_uniformed_batch(
        self, city: str, batch_size: int, last_trajectory_id: int | None
    ) -> list[dict[str, Any]]:
        """Fetch a batch of a city's uniformed trajectories ordered by trajectory_id."""
        cursor = self.connection.cursor(row_factory=dict_row)
        try:
            base = """
                SELECT u.trajectory_id, u.vehicle_id, vt.name AS vehicle_type,
                    u.trajectory_date, u.city, u.points, u.source_id, s.dataset_id
                FROM uniformed_trajectories u
                JOIN source_trajectories s ON s.source_id = u.source_id
                LEFT JOIN vehicle_types vt ON u.vehicle_type_id = vt.vehicle_type_id
                WHERE u.city = %s
            """
            if last_trajectory_id is None:
                cursor.execute(base + " ORDER BY u.trajectory_id LIMIT %s", (city, batch_size))
            else:
                cursor.execute(
                    base + " AND u.trajectory_id > %s ORDER BY u.trajectory_id LIMIT %s",
                    (city, last_trajectory_id, batch_size),
                )
            rows = cursor.fetchall()
            return rows
        except Exception as error:
            print(f"Failed to retrieve uniformed batch: {error}")
            raise
        finally:
            cursor.close()

    def insert_cleaned_uniformed_trajectories(self, trajectories: list[UniformedTrajectories]) -> None:
        """Bulk-insert cleaned trajectory runs into the cleaned_uniformed_trajectories table."""
        vehicle_type_ids = self.get_vehicle_type_ids()
        cursor = self.connection.cursor()
        try:
            values = []
            for trajectory in trajectories:
                points = []

                for point in trajectory.points:
                    points.append(
                        {
                            "longitude": point.longitude,
                            "latitude": point.latitude,
                            "point_timestamp": to_utc_iso(point.point_timestamp),
                        }
                    )

                values.append(
                    (
                        trajectory.vehicle_id,
                        vehicle_type_ids[trajectory.vehicle_type],
                        trajectory.trajectory_date,
                        trajectory.city,
                        Jsonb(points),
                        trajectory.source_id,
                    )
                )

            cursor.executemany(
                "INSERT INTO cleaned_uniformed_trajectories "
                "(vehicle_id, vehicle_type_id, trajectory_date, city, points, source_id) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                values,
            )
        except Exception as error:
            print(f"Failed to insert cleaned uniformed trajectories: {error}")
            raise
        finally:
            cursor.close()

    def insert_data_uniformed_trajectories(self, trajectories: list[UniformedTrajectories]) -> None:
        """Insert uniformed trajectories into the database."""
        vehicle_type_ids = self.get_vehicle_type_ids()
        cursor = self.connection.cursor()

        try:
            values = []
            for trajectory in trajectories:
                points = []

                for point in trajectory.points:
                    points.append(
                        {
                            "longitude": point.longitude,
                            "latitude": point.latitude,
                            "point_timestamp": to_utc_iso(point.point_timestamp),
                        }
                    )

                values.append(
                    (
                        trajectory.vehicle_id,
                        vehicle_type_ids[trajectory.vehicle_type],
                        trajectory.trajectory_date,
                        trajectory.city,
                        Jsonb(points),
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

    def get_vehicle_type_ids(self) -> dict[str, int]:
        """Fetch vehicle type IDs from the database."""
        cursor = self.connection.cursor()

        try:
            cursor.execute("SELECT name, vehicle_type_id FROM vehicle_types")
            return dict(cursor.fetchall())
        except Exception as error:
            print(f"Failed to retrieve vehicle types from database: {error}")
            raise
        finally:
            cursor.close()

    def insert_segments_into_db(self, segments: list[TrajectorySegments]) -> None:
        """Inserts segments into tabel in database"""
        cursor = self.connection.cursor()

        try:
            rows = []

            for t_segment in segments:
                rows.append(
                    (
                        t_segment.trajectory_id,
                        t_segment.segment_index,
                        t_segment.path,
                        t_segment.start_time,
                        t_segment.end_time,
                    )
                )

            cursor.executemany(
                """
            INSERT IGNORE INTO trajectory_segments (
                trajectory_id,
                segment_index,
                path,
                start_time,
                end_time)
                VALUES (%s, %s, ST_GeomFromText(%s, 4326, 'axis-order=long-lat'), %s, %s)
                """,
                rows,
            )
        except Exception as error:
            print(f"Failed to insert segments into database: {error}")
            raise
        finally:
            cursor.close()

    async def retrieve_cleaned_uniformed_batch(
        self, batch_size: int, last_trajectory_id: int | None
    ) -> list[dict[str, Any]]:
        """Fetch a batch of cleaned uniformed trajectories ordered by trajectory_id."""
        cursor = self.connection.cursor(row_factory=dict_row)
        try:
            base = """
                SELECT u.trajectory_id, u.points
                FROM cleaned_uniformed_trajectories u
            """

            if last_trajectory_id is None:
                query = base + " ORDER BY u.trajectory_id LIMIT %s"
                params = (batch_size,)
            else:
                query = (
                    base
                    + """
                    WHERE u.trajectory_id > %s
                    ORDER BY u.trajectory_id
                    LIMIT %s
                """
                )
                params = (last_trajectory_id, batch_size)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            return rows

        except Exception as error:
            print(f"Failed to retrieve cleaned uniformed batch: {error}")
            raise
        finally:
            cursor.close()

    def get_candidate_segments(
        self,
        box_a: BoundingBox,
        box_b: BoundingBox,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Fetch the segments near box A or box B, for trips that come near both, in the date range."""
        cursor = self.connection.cursor(row_factory=dict_row)

        try:
            day_after_end = end_date + timedelta(days=1)

            sql = """
                WITH hits AS (
                    SELECT trajectory_id, segment_index,
                        (min_longitude <= %(a_max_longitude)s AND max_longitude >= %(a_min_longitude)s
                            AND min_latitude <= %(a_max_latitude)s AND max_latitude >= %(a_min_latitude)s)
                            AS in_a,
                        (min_longitude <= %(b_max_longitude)s AND max_longitude >= %(b_min_longitude)s
                            AND min_latitude <= %(b_max_latitude)s AND max_latitude >= %(b_min_latitude)s)
                            AS in_b
                    FROM trajectory_segments FORCE INDEX (idx_segment_time_bounds)
                    WHERE start_time >= %(start_date)s
                    AND start_time < %(day_after_end)s
                    AND ((min_longitude <= %(a_max_longitude)s AND max_longitude >= %(a_min_longitude)s
                            AND min_latitude <= %(a_max_latitude)s AND max_latitude >= %(a_min_latitude)s)
                        OR (min_longitude <= %(b_max_longitude)s AND max_longitude >= %(b_min_longitude)s
                            AND min_latitude <= %(b_max_latitude)s AND max_latitude >= %(b_min_latitude)s))
                ),
                both_boxes AS (
                    SELECT trajectory_id
                    FROM hits
                    GROUP BY trajectory_id
                    HAVING MAX(in_a) = 1 AND MAX(in_b) = 1
                )
                SELECT s.trajectory_id, s.segment_index, s.start_time, s.end_time,
                    ST_Longitude(ST_StartPoint(s.path)) AS start_longitude,
                    ST_Latitude(ST_StartPoint(s.path))  AS start_latitude,
                    ST_Longitude(ST_EndPoint(s.path))   AS end_longitude,
                    ST_Latitude(ST_EndPoint(s.path))    AS end_latitude
                FROM hits h
                JOIN both_boxes b ON b.trajectory_id = h.trajectory_id
                JOIN trajectory_segments s
                ON s.trajectory_id = h.trajectory_id
                AND s.segment_index = h.segment_index
                ORDER BY s.trajectory_id, s.segment_index
            """

            values = {
                "start_date": start_date,
                "day_after_end": day_after_end,
                "a_min_longitude": box_a.min_longitude,
                "a_min_latitude": box_a.min_latitude,
                "a_max_longitude": box_a.max_longitude,
                "a_max_latitude": box_a.max_latitude,
                "b_min_longitude": box_b.min_longitude,
                "b_min_latitude": box_b.min_latitude,
                "b_max_longitude": box_b.max_longitude,
                "b_max_latitude": box_b.max_latitude,
            }

            cursor.execute(sql, values)

            return cursor.fetchall()
        except Exception as error:
            print(f"Failed to get candidate segments: {error}")
            raise
        finally:
            cursor.close()

    def get_trajectory_points(self, trajectory_ids: list[int]) -> dict[int, list[UniformedTrajectoryPoint]]:
        """Fetch all points of the given trips, as one list per trip"""
        if len(trajectory_ids) == 0:
            return {}

        cursor = self.connection.cursor(row_factory=dict_row)

        try:
            sql = """
                SELECT trajectory_id, points
                FROM cleaned_uniformed_trajectories
                WHERE trajectory_id = ANY(%s)
            """

            cursor.execute(sql, (trajectory_ids,))

            points_by_trip: dict[int, list[UniformedTrajectoryPoint]] = {}

            for row in cursor.fetchall():
                points = []

                for point in row["points"]:
                    points.append(
                        UniformedTrajectoryPoint(
                            longitude=point["longitude"],
                            latitude=point["latitude"],
                            point_timestamp=datetime.fromisoformat(point["point_timestamp"]),
                        )
                    )

                points_by_trip[row["trajectory_id"]] = points

            return points_by_trip
        except Exception as error:
            print(f"Failed to get trip points: {error}")
            raise
        finally:
            cursor.close()
