import asyncio
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from database.repositories.dataset_repository import DatasetRepository
from database.repositories.import_repository import ImportRepository
from database.repositories.trajectory_repository import TrajectoryRepository
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
    return DatasetRepository(context).create_dataset("x", 1)


def _call_get_or_create_city(context):
    return DatasetRepository(context).get_or_create_city("x", "Europe/Lisbon")


def _call_get_time_zones(context):
    return DatasetRepository(context).get_time_zones()


def _call_get_trajectories_cities_from_db(context):
    return DatasetRepository(context).get_trajectories_cities_from_db()


def _call_get_vehicle_type_ids(context):
    return TrajectoryRepository(context).get_vehicle_type_ids()


def _call_insert_trips(context):
    now = datetime.now(UTC)
    return TrajectoryRepository(context).insert_trips(
        [1], [UniformedTrajectories(1, VehicleType.CAR, now, [UniformedTrajectoryPoint(1, now, 2)])]
    )


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
        _call_get_or_create_city,
        _call_get_time_zones,
        _call_get_trajectories_cities_from_db,
        _call_get_vehicle_type_ids,
        _call_insert_trips,
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
        datetime.now(UTC),
        [UniformedTrajectoryPoint(1, datetime.now(UTC), 2)],
    )

    with pytest.raises(RuntimeError):
        TrajectoryRepository(context).insert_data_uniformed_trajectories([trajectory])

    type_cursor.close.assert_called_once()
    insert_cursor.close.assert_called_once()
