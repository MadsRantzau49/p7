from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from helpers.time_helper import to_utc_iso
from models.bounding_box import BoundingBox
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
                                   t.source_id,
                                   z.time_zone
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
            rows = cursor.fetchall()

            if not rows:
                return []

            zone = ZoneInfo(rows[0]["time_zone"])

            return [
                UniformedTrajectories(
                    trajectory_id=trajectory["trajectory_id"],
                    vehicle_id=trajectory["vehicle_id"],
                    vehicle_type=VehicleType(trajectory["vehicle_type"]),
                    trajectory_date=trajectory["trajectory_date"].astimezone(zone),
                    city=trajectory["city"],
                    points=[
                        UniformedTrajectoryPoint(
                            longitude=point["longitude"],
                            latitude=point["latitude"],
                            point_timestamp=datetime.fromisoformat(point["point_timestamp"]).astimezone(zone),
                        )
                        for point in trajectory["points"]
                    ],
                    source_id=trajectory["source_id"],
                )
                for trajectory in rows
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

    def insert_cleaned_uniformed_trajectories(self, trajectories: list[UniformedTrajectories]) -> list[int]:
        """Bulk-insert cleaned trajectory runs and return their new trajectory_ids, in the same order."""
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
                    "INSERT INTO cleaned_uniformed_trajectories "
                    "(vehicle_id, vehicle_type_id, trajectory_date, city, points, source_id) "
                    "VALUES (%s, %s, %s, %s, %s, %s) "
                    "RETURNING trajectory_id"
                ),
                values,
                returning=True,
            )

            trajectory_ids = []
            for result in cursor.results():
                for row in result.fetchall():
                    trajectory_ids.append(row[0])

            return trajectory_ids
        except Exception as error:
            print(f"Failed to insert cleaned uniformed trajectories: {error}")
            raise
        finally:
            cursor.close()

    def insert_trips(self, trajectory_ids: list[int], trajectories: list[UniformedTrajectories]) -> None:
        """Insert each cleaned trajectory into trips as a MobilityDB trip under its trajectory_id."""
        cursor = self.connection.cursor()

        try:
            values = []
            for trajectory_id, trajectory in zip(trajectory_ids, trajectories, strict=True):
                instants = []

                for point in trajectory.points:
                    instants.append(
                        f"POINT({point.longitude} {point.latitude})@{to_utc_iso(point.point_timestamp)}"
                    )

                trip = "SRID=4326;[" + ", ".join(instants) + "]"
                values.append((trajectory_id, trip))

            cursor.executemany("INSERT INTO trips (trajectory_id, trip) VALUES (%s, %s)", values)

        except Exception as error:
            print(f"Failed to insert trips: {error}")
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

    def get_subtrajectories(
        self, box_a: BoundingBox, box_b: BoundingBox, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        """Fetch every part of a trip that leaves box A and then enters box B.

        The search window is one day wider on each side than the date range, because the dates
        are local to each city. The service keeps only the ones that leave A inside the date range.
        """
        cursor = self.connection.cursor(row_factory=dict_row)

        try:
            area_a = sql.SQL(
                "ST_MakeEnvelope(%(a_min_lon)s, %(a_min_lat)s, %(a_max_lon)s, %(a_max_lat)s, 4326)"
            )
            area_b = sql.SQL(
                "ST_MakeEnvelope(%(b_min_lon)s, %(b_min_lat)s, %(b_max_lon)s, %(b_max_lat)s, 4326)"
            )
            search_window = sql.SQL("span(%(search_start)s, %(search_end)s)")

            query = sql.SQL("""
            WITH pieces AS (
                SELECT trips.trajectory_id,
                       trips.trip,
                       cleaned.points,
                       cities.time_zone,
                       unnest(sequences(minusGeometry(trips.trip, ST_Union({area_a}, {area_b})))) AS piece
                FROM trips
                         JOIN cleaned_uniformed_trajectories AS cleaned USING (trajectory_id)
                         JOIN cities ON cities.name = cleaned.city
                WHERE trips.trip && stbox({area_a}, {search_window})
                  AND trips.trip && stbox({area_b}, {search_window})
                  AND eIntersects(trips.trip, {area_a})
                  AND eIntersects(trips.trip, {area_b}))
            SELECT trajectory_id,
                   points,
                   time_zone,
                   startTimestamp(piece)   AS exit_a_time,
                   endTimestamp(piece)     AS entry_b_time,
                   ST_X(startValue(piece)) AS exit_a_longitude,
                   ST_Y(startValue(piece)) AS exit_a_latitude,
                   ST_X(endValue(piece))   AS entry_b_longitude,
                   ST_Y(endValue(piece))   AS entry_b_latitude
            FROM pieces
            WHERE startTimestamp(piece) > startTimestamp(trip)
              AND endTimestamp(piece) < endTimestamp(trip)
              AND ST_Distance(startValue(piece), {area_a}) < ST_Distance(startValue(piece), {area_b})
              AND ST_Distance(endValue(piece), {area_b}) < ST_Distance(endValue(piece), {area_a})
            ORDER BY trajectory_id, exit_a_time
            """).format(area_a=area_a, area_b=area_b, search_window=search_window)

            values = {
                "a_min_lon": box_a.min_longitude,
                "a_min_lat": box_a.min_latitude,
                "a_max_lon": box_a.max_longitude,
                "a_max_lat": box_a.max_latitude,
                "b_min_lon": box_b.min_longitude,
                "b_min_lat": box_b.min_latitude,
                "b_max_lon": box_b.max_longitude,
                "b_max_lat": box_b.max_latitude,
                "search_start": datetime.combine(start_date - timedelta(days=1), time.min, UTC),
                "search_end": datetime.combine(end_date + timedelta(days=2), time.min, UTC),
            }

            cursor.execute(query, values)

            return cursor.fetchall()
        except Exception as error:
            print(f"Failed to get subtrajectories: {error}")
            raise
        finally:
            cursor.close()
