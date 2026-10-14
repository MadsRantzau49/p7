import asyncio
import uuid
from datetime import datetime, time, timedelta
from unittest.mock import MagicMock

import pytest
from database.connection import create_db_connection
from database.repositories.dataset_repository import DatasetRepository
from database.repositories.import_repository import ImportRepository
from database.repositories.trajectory_repository import TrajectoryRepository
from models.beijing_trajectory import BeijingTrajectory, TrajectoryPoint
from models.porto_trajectory import PortoTrajectory
from models.uniformed_trajectories import UniformedTrajectories, UniformedTrajectoryPoint
from models.upload_row import VehicleType


def _call_get_dataset_id(context):
    return DatasetRepository(context).get_dataset_id("x")


def _call_create_source_trajectories(context):
    return TrajectoryRepository(context).create_source_trajectories(1, ["x"])


def _call_insert_porto_trajectories(context):
    return ImportRepository(context).insert_porto_trajectories([])


def _call_insert_beijing_dataset(context):
    return ImportRepository(context).insert_beijing_dataset([])


def _call_retrieve_porto_dataset_batch(context):
    return ImportRepository(context).retrieve_porto_dataset_batch(1, None)


def _call_retrieve_beijing_data_batch(context):
    return ImportRepository(context).retrieve_beijing_data_batch(1, None)


def _call_get_trajectories_from_db(context):
    return asyncio.run(
        TrajectoryRepository(context).get_trajectories_from_db("x", None, None, None, None, None)
    )


def _call_dataset_name_taken(context):
    return DatasetRepository(context).dataset_name_taken("x")


def _call_create_dataset(context):
    return DatasetRepository(context).create_dataset("x")


def _call_get_trajectories_cities_from_db(context):
    return asyncio.run(DatasetRepository(context).get_trajectories_cities_from_db())


def _call_get_vehicle_type_ids(context):
    return TrajectoryRepository(context).get_vehicle_type_ids()


def test_queries_against_configured_database():
    """Run every query against the database configured by .env."""
    context = create_db_connection()
    dataset_repository = DatasetRepository(context)
    trajectory_repository = TrajectoryRepository(context)
    import_repository = ImportRepository(context)

    name = f"pytest-{uuid.uuid4()}"
    source_ids = [str(uuid.uuid4()) for _ in range(3)]
    now = datetime.now().replace(microsecond=0)

    try:
        assert {"CAR", "TAXI", "UNKNOWN"} <= trajectory_repository.get_vehicle_type_ids().keys()
        assert isinstance(asyncio.run(dataset_repository.get_trajectories_cities_from_db()), list)
        assert not dataset_repository.dataset_name_taken(name)

        dataset_id = dataset_repository.create_dataset(name)
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
        assert isinstance(result[0].points[0], UniformedTrajectoryPoint)

        assert isinstance(
            asyncio.run(
                trajectory_repository.get_trajectories_from_db(name, None, None, time(23), time(2), None)
            ),
            list,
        )
    finally:
        context.rollback()
        context.close()


@pytest.mark.parametrize(
    "call_query",
    [
        _call_get_dataset_id,
        _call_create_source_trajectories,
        _call_insert_porto_trajectories,
        _call_insert_beijing_dataset,
        _call_retrieve_porto_dataset_batch,
        _call_retrieve_beijing_data_batch,
        _call_get_trajectories_from_db,
        _call_dataset_name_taken,
        _call_create_dataset,
        _call_get_trajectories_cities_from_db,
        _call_get_vehicle_type_ids,
    ],
)
def test_query_errors_are_raised_and_cursors_closed(call_query):
    """Ensure query errors propagate after closing their cursors."""
    context = MagicMock()
    cursor = context.cursor.return_value
    cursor.execute.side_effect = cursor.executemany.side_effect = RuntimeError("database error")

    with pytest.raises(RuntimeError):
        call_query(context)

    cursor.close.assert_called_once()


def test_uniformed_insert_error_is_raised_and_cursor_closed():
    """Ensure a uniformed insert error propagates and closes its cursor."""
    context = MagicMock()
    type_cursor = MagicMock()
    type_cursor.fetchall.return_value = [("CAR", 1)]
    insert_cursor = MagicMock()
    insert_cursor.executemany.side_effect = RuntimeError("database error")
    context.cursor.side_effect = [type_cursor, insert_cursor]

    trajectory = UniformedTrajectories(
        1,
        VehicleType.CAR,
        datetime.now(),
        [UniformedTrajectoryPoint(1, datetime.now(), 2)],
    )

    with pytest.raises(RuntimeError):
        TrajectoryRepository(context).insert_data_uniformed_trajectories([trajectory])

    type_cursor.close.assert_called_once()
    insert_cursor.close.assert_called_once()
