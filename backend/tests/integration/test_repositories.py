import asyncio
import uuid
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from database.connection import create_db_connection
from database.repositories.dataset_repository import DatasetRepository
from database.repositories.import_repository import ImportRepository
from database.repositories.trajectory_repository import TrajectoryRepository
from models.beijing_trajectory import BeijingTrajectory, TrajectoryPoint
from models.bounding_box import BoundingBox
from models.porto_trajectory import PortoTrajectory
from models.uniformed_trajectories import UniformedTrajectories, UniformedTrajectoryPoint
from models.upload_row import VehicleType


def test_queries_against_configured_database():
    """Run every query against the configured database, then undo all changes"""
    name = f"pytest-{uuid.uuid4()}"
    source_ids = [str(uuid.uuid4()) for _ in range(3)]
    now = datetime.now(UTC).replace(microsecond=0)

    with create_db_connection() as connection:
        dataset_repository = DatasetRepository(connection)
        trajectory_repository = TrajectoryRepository(connection)
        import_repository = ImportRepository(connection)

        try:
            assert {"CAR", "TAXI", "UNKNOWN"} <= trajectory_repository.get_vehicle_type_ids().keys()
            assert "Europe/Lisbon" in dataset_repository.get_time_zones()
            assert not dataset_repository.dataset_name_taken(name)

            city = dataset_repository.get_or_create_city(name, "Europe/Lisbon")
            assert dataset_repository.get_or_create_city(name, "Europe/Copenhagen") == city
            assert city in dataset_repository.get_trajectories_cities_from_db()

            dataset_id = dataset_repository.create_dataset(name, city.city_id)
            assert dataset_repository.get_dataset_id(name) == dataset_id
            assert dataset_repository.dataset_name_taken(name)

            trajectory_repository.create_source_trajectories(dataset_id, source_ids)

            import_repository.insert_porto_trajectories(
                [PortoTrajectory(1, None, None, None, 1, 1, None, False, [[1.0, 2.0]], source_ids[0])]
            )
            import_repository.insert_beijing_dataset(
                [BeijingTrajectory(1, [TrajectoryPoint(str(now), "1", "2")], source_ids[1])]
            )
            trajectory_repository.insert_data_uniformed_trajectories(
                [
                    UniformedTrajectories(
                        1,
                        VehicleType.CAR,
                        now,
                        [UniformedTrajectoryPoint(1, now, 2)],
                        city=name,
                        source_id=source_ids[2],
                    )
                ]
            )

            later = now + timedelta(seconds=15)
            cleaned = [
                UniformedTrajectories(
                    1,
                    VehicleType.CAR,
                    now,
                    [UniformedTrajectoryPoint(1, now, 2), UniformedTrajectoryPoint(1.5, later, 2.5)],
                    city=name,
                    source_id=source_ids[2],
                )
            ]
            trajectory_ids = trajectory_repository.insert_cleaned_uniformed_trajectories(cleaned)
            trajectory_repository.insert_trips(trajectory_ids, cleaned)
            trip = connection.execute(
                "SELECT numInstants(trips.trip), startTimestamp(trips.trip) FROM trips "
                "JOIN cleaned_uniformed_trajectories AS cleaned USING (trajectory_id) "
                "WHERE cleaned.source_id = %s",
                (source_ids[2],),
            ).fetchone()
            assert trip == (2, now)

            assert isinstance(import_repository.retrieve_porto_dataset_batch(1, None), list)
            assert isinstance(import_repository.retrieve_porto_dataset_batch(1, ""), list)
            assert isinstance(import_repository.retrieve_beijing_data_batch(1, None), list)
            assert isinstance(import_repository.retrieve_beijing_data_batch(1, ""), list)

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
    source_id = str(uuid.uuid4())
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
            trajectory_repository.create_source_trajectories(dataset_id, [source_id])
            cleaned = [
                UniformedTrajectories(1, VehicleType.TAXI, start, points, city=name, source_id=source_id)
            ]
            [trajectory_id] = trajectory_repository.insert_cleaned_uniformed_trajectories(cleaned)
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
        finally:
            connection.rollback()
