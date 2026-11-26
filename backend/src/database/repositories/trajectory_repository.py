from collections.abc import Generator, Iterator
from contextlib import closing, contextmanager
from datetime import date, datetime, time, timedelta
from typing import Any, cast
from zoneinfo import ZoneInfo

from helpers.time_helper import to_utc_iso
from models.bounding_box import BoundingBox
from models.uniformed_trajectories import UniformedTrajectories, UniformedTrajectoryPoint, VehicleType
from psycopg import Connection, sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from services.logging import Logging


class TrajectoryRepository(Logging):
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
                                   t.vehicle_type,
                                   t.trajectory_date,
                                   t.city,
                                   t.points,
                                   z.time_zone
                            FROM uniformed_trajectories AS t
                                     CROSS JOIN z
                                     CROSS JOIN LATERAL (
                                SELECT t.trajectory_date AT TIME ZONE z.time_zone AS local_start,
                                    (t.points -> -1 ->> 'point_timestamp') ::timestamptz
                                    AT TIME ZONE z.time_zone AS local_end
                                ) AS l
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
                )
                for trajectory in rows
            ]

        except Exception as error:
            print(f"Failed to get trajectories from database: {error}")
            raise
        finally:
            cursor.close()

    def insert_uniformed_trajectories(
        self, dataset_id: int, trajectories: list[UniformedTrajectories]
    ) -> list[int]:
        """Bulk-insert cleaned trajectory runs and return their new trajectory_ids, in the same order."""
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
                        dataset_id,
                        trajectory.vehicle_id,
                        trajectory.vehicle_type.value,
                        trajectory.trajectory_date,
                        trajectory.city,
                        Jsonb(points),
                    )
                )

            cursor.executemany(
                (
                    "INSERT INTO uniformed_trajectories "
                    "(dataset_id, vehicle_id, vehicle_type, trajectory_date, city, points) "
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

    def get_subtrajectories(
        self,
        box_a: BoundingBox,
        box_b: BoundingBox,
        start_date: date | None,
        end_date: date | None,
        start_time: time | None = None,
        end_time: time | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch every part of a trip that leaves box A and then enters box B.

        The search window is one day wider on each side than the date range, because the dates
        are local to each city. The service keeps only the ones that leave A inside the date range.
        Missing date bounds are unbounded.

        If start_time or end_time is given, only parts that leave A between them (in the city's
        local time) are returned. If start_time is after end_time, the window wraps around midnight.
        """
        with self.stream_subtrajectories(box_a, box_b, start_date, end_date, start_time, end_time) as rows:
            return list(rows)

    @contextmanager
    def stream_subtrajectories(
        self,
        box_a: BoundingBox,
        box_b: BoundingBox,
        start_date: date | None,
        end_date: date | None,
        start_time: time | None = None,
        end_time: time | None = None,
    ) -> Iterator[Iterator[dict[str, Any]]]:
        """Stream the same ordered statement without buffering the full result client-side."""
        self.log_heading()
        query, values = self._subtrajectory_statement(
            box_a, box_b, start_date, end_date, start_time, end_time
        )
        with self.connection.cursor(row_factory=dict_row) as cursor:
            # psycopg types stream() as Iterator, but implements it as a generator.
            stream = cast(Generator[dict[str, Any], None, None], cursor.stream(query, values))
            with closing(stream):
                yield stream

    @staticmethod
    def _subtrajectory_statement(
        box_a: BoundingBox,
        box_b: BoundingBox,
        start_date: date | None,
        end_date: date | None,
        start_time: time | None,
        end_time: time | None,
    ) -> tuple[sql.Composed, dict[str, float | date | time | None]]:
        area_a = sql.SQL("ST_MakeEnvelope(%(a_min_lon)s, %(a_min_lat)s, %(a_max_lon)s, %(a_max_lat)s, 4326)")
        area_b = sql.SQL("ST_MakeEnvelope(%(b_min_lon)s, %(b_min_lat)s, %(b_max_lon)s, %(b_max_lat)s, 4326)")
        search_window = sql.SQL("""
                span(
                    COALESCE((%(start_date)s::timestamp AT TIME ZONE 'UTC') - INTERVAL '1 day',
                             '-infinity'::timestamptz),
                    COALESCE((%(end_date)s::timestamp AT TIME ZONE 'UTC') + INTERVAL '2 days',
                             'infinity'::timestamptz)
                )
            """)

        time_filter = sql.SQL("")
        if start_time is not None or end_time is not None:
            start_time = start_time or time.min
            end_time = end_time or time.max
            exit_a_local_time = "(startTimestamp(piece) AT TIME ZONE time_zone)::time"
            if start_time <= end_time:
                condition = f"{exit_a_local_time} BETWEEN %(start_time)s AND %(end_time)s"
            else:
                condition = f"({exit_a_local_time} >= %(start_time)s OR {exit_a_local_time} <= %(end_time)s)"
            time_filter = sql.SQL("AND " + condition)

        query = sql.SQL("""
            WITH pieces AS (
                SELECT trips.trajectory_id,
                       trips.trip,
                       uniformed.points,
                       cities.time_zone,
                       unnest(sequences(minusGeometry(trips.trip, ST_Union({area_a}, {area_b})))) AS piece
                FROM trips
                         JOIN uniformed_trajectories AS uniformed USING (trajectory_id)
                         JOIN cities ON cities.name = uniformed.city
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
              {time_filter}
            ORDER BY trajectory_id, exit_a_time
            """).format(area_a=area_a, area_b=area_b, search_window=search_window, time_filter=time_filter)

        return query, {
            "a_min_lon": box_a.min_longitude,
            "a_min_lat": box_a.min_latitude,
            "a_max_lon": box_a.max_longitude,
            "a_max_lat": box_a.max_latitude,
            "b_min_lon": box_b.min_longitude,
            "b_min_lat": box_b.min_latitude,
            "b_max_lon": box_b.max_longitude,
            "b_max_lat": box_b.max_latitude,
            "start_date": start_date,
            "end_date": end_date,
            "start_time": start_time,
            "end_time": end_time,
        }
