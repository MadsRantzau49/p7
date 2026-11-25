import asyncio
import uuid
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from database.connection import create_db_connection
from database.repositories.dataset_repository import DatasetRepository
from database.repositories.trajectory_repository import TrajectoryRepository
from models.bounding_box import BoundingBox
from models.uniformed_trajectories import UniformedTrajectories, UniformedTrajectoryPoint, VehicleType


def test_queries_against_configured_database():
    """Run every query against the configured database, then undo all changes"""
    name = f"pytest-{uuid.uuid4()}"
    # Fixed noon time, so the 15 second trajectory never crosses midnight in the city's zone
    now = datetime(2024, 1, 15, 12, 0, tzinfo=UTC)

    with create_db_connection() as connection:
        dataset_repository = DatasetRepository(connection)
        trajectory_repository = TrajectoryRepository(connection)

        try:
            city = dataset_repository.get_or_create_city(name, "Europe/Lisbon")
            assert dataset_repository.get_or_create_city(name, "Europe/Copenhagen") == city
            assert city in dataset_repository.get_trajectories_cities_from_db()

            dataset_id = dataset_repository.create_dataset(name, city.city_id)

            later = now + timedelta(seconds=15)
            cleaned = [
                UniformedTrajectories(
                    "1",
                    VehicleType.CAR,
                    now,
                    [UniformedTrajectoryPoint(1, now, 2), UniformedTrajectoryPoint(1.5, later, 2.5)],
                    city=name,
                )
            ]
            trajectory_ids = trajectory_repository.insert_uniformed_trajectories(dataset_id, cleaned)
            trajectory_repository.insert_trips(trajectory_ids, cleaned)
            trip = connection.execute(
                "SELECT numInstants(trip), startTimestamp(trip) FROM trips WHERE trajectory_id = %s",
                (trajectory_ids[0],),
            ).fetchone()
            assert trip == (2, now)

            assert (
                len(
                    asyncio.run(
                        trajectory_repository.get_trajectories_from_db(name, None, None, None, None, None)
                    )
                )
                == 1
            )

            result = asyncio.run(
                trajectory_repository.get_trajectories_from_db(
                    name,
                    (now - timedelta(days=1)).date(),
                    (now + timedelta(days=1)).date(),
                    time.min,
                    time.max,
                    1,
                )
            )
            assert len(result) == 1
            assert isinstance(result[0], UniformedTrajectories)
            assert result[0].trajectory_date == now
            assert result[0].trajectory_date.tzinfo == ZoneInfo("Europe/Lisbon")
            assert isinstance(result[0].points[0], UniformedTrajectoryPoint)
            assert result[0].points[0].point_timestamp.tzinfo == ZoneInfo("Europe/Lisbon")

            assert isinstance(
                asyncio.run(
                    trajectory_repository.get_trajectories_from_db(name, None, None, time(23), time(2), None)
                ),
                list,
            )
        finally:
            connection.rollback()


def test_get_subtrajectories_against_configured_database():
    """Cut a straight trip between two boxes at the expected time and places, then undo all changes."""
    name = f"pytest-{uuid.uuid4()}"
    start = datetime(2013, 7, 1, 8, 10, tzinfo=UTC)

    points = [
        UniformedTrajectoryPoint(-8.62 + 0.01 * minute, start + timedelta(minutes=minute), 41.15)
        for minute in range(4)
    ]
    box_a = BoundingBox(-8.616, 41.14, -8.612, 41.16)
    box_b = BoundingBox(-8.598, 41.14, -8.594, 41.16)

    with create_db_connection() as connection:
        dataset_repository = DatasetRepository(connection)
        trajectory_repository = TrajectoryRepository(connection)

        try:
            city = dataset_repository.get_or_create_city(name, "Europe/Lisbon")
            dataset_id = dataset_repository.create_dataset(name, city.city_id)
            cleaned = [UniformedTrajectories("1", VehicleType.TAXI, start, points, city=name)]
            [trajectory_id] = trajectory_repository.insert_uniformed_trajectories(dataset_id, cleaned)
            trajectory_repository.insert_trips([trajectory_id], cleaned)

            def subtrajectories(start_date, end_date):
                rows = trajectory_repository.get_subtrajectories(box_a, box_b, start_date, end_date)
                return [found for found in rows if found["trajectory_id"] == trajectory_id]

            [found] = subtrajectories(date(2013, 7, 1), date(2013, 7, 1))

            assert abs(found["exit_a_time"] - (start + timedelta(seconds=48))) < timedelta(milliseconds=1)
            assert abs(found["entry_b_time"] - (start + timedelta(seconds=132))) < timedelta(milliseconds=1)
            assert found["exit_a_longitude"] == pytest.approx(-8.612)
            assert found["entry_b_longitude"] == pytest.approx(-8.598)
            assert len(found["points"]) == 4
            assert found["time_zone"] == "Europe/Lisbon"

            assert subtrajectories(date(2013, 6, 20), date(2013, 6, 20)) == []

            for start_date, end_date in [
                (None, None),
                (date(2013, 7, 1), None),
                (None, date(2013, 7, 1)),
            ]:
                [unbounded] = subtrajectories(start_date, end_date)
                assert unbounded["trajectory_id"] == trajectory_id
                assert unbounded["exit_a_time"] == found["exit_a_time"]

            assert subtrajectories(date(2013, 7, 3), None) == []
            assert subtrajectories(None, date(2013, 6, 28)) == []

            overnight = trajectory_repository.get_subtrajectories(
                box_a, box_b, None, None, time(22), time(10)
            )
            assert trajectory_id in [row["trajectory_id"] for row in overnight]
            excluded = trajectory_repository.get_subtrajectories(box_a, box_b, None, None, time(22), time(2))
            assert trajectory_id not in [row["trajectory_id"] for row in excluded]
        finally:
            connection.rollback()
