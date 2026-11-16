import asyncio
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from database.repositories.dataset_repository import DatasetRepository
from database.repositories.trajectory_repository import TrajectoryRepository
from models.uniformed_trajectories import UniformedTrajectories, UniformedTrajectoryPoint, VehicleType


def _trajectory():
    now = datetime.now(UTC)
    return UniformedTrajectories(1, VehicleType.CAR, now, [UniformedTrajectoryPoint(1, now, 2)])


def _call_get_trajectories_from_db(context):
    return asyncio.run(
        TrajectoryRepository(context).get_trajectories_from_db("x", None, None, None, None, None)
    )


def _call_insert_uniformed_trajectories(context):
    return TrajectoryRepository(context).insert_uniformed_trajectories(1, [_trajectory()])


def _call_insert_trips(context):
    return TrajectoryRepository(context).insert_trips([1], [_trajectory()])


def _call_create_dataset(context):
    return DatasetRepository(context).create_dataset("x", 1)


def _call_delete_dataset(context):
    return DatasetRepository(context).delete_dataset(1)


def _call_get_or_create_city(context):
    return DatasetRepository(context).get_or_create_city("x", "Europe/Lisbon")


def _call_get_trajectories_cities_from_db(context):
    return DatasetRepository(context).get_trajectories_cities_from_db()


@pytest.mark.parametrize(
    "call_query",
    [
        _call_get_trajectories_from_db,
        _call_insert_uniformed_trajectories,
        _call_insert_trips,
        _call_create_dataset,
        _call_delete_dataset,
        _call_get_or_create_city,
        _call_get_trajectories_cities_from_db,
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
