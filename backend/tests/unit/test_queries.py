import asyncio
import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
from database.connection import create_db_connection
from models.beijing_trajectory import BeijingTrajectory, TrajectoryPoint
from models.porto_trajectory import PortoTrajectory
from models.uniformed_trajectories import UniformedTrajectories, UniformedTrajectoryPoint
from models.upload_row import VehicleType

from database import queries


def test_queries_against_configured_database():
    """Run every query against the database configured by .env."""
    context = create_db_connection()
    name = f"pytest-{uuid.uuid4()}"
    source_ids = [str(uuid.uuid4()) for _ in range(3)]
    now = datetime.now().replace(microsecond=0)

    try:
        assert {"CAR", "TAXI", "UNKNOWN"} <= queries.get_vehicle_type_ids(context).keys()
        assert isinstance(asyncio.run(queries.get_trajectories_cities_from_db(context)), list)
        assert not queries.dataset_name_taken(context, name)

        dataset_id = queries.create_dataset(context, name)
        assert queries.get_dataset_id(context, name) == dataset_id
        assert queries.dataset_name_taken(context, name)
        queries.create_source_trajectories(context, dataset_id, source_ids)

        queries.insert_porto_trajectories(
            context,
            [PortoTrajectory(1, None, None, None, 1, 1, None, False, [[1.0, 2.0]], source_ids[0])],
        )
        queries.insert_beijing_dataset(
            context,
            [BeijingTrajectory(1, [TrajectoryPoint(str(now), "1", "2")], source_ids[1])],
        )
        queries.insert_data_uniformed_trajectories(
            context,
            [
                UniformedTrajectories(
                    1,
                    VehicleType.CAR,
                    now,
                    [UniformedTrajectoryPoint(1, now, 2)],
                    city=name,
                    source_id=source_ids[2],
                )
            ],
        )

        assert isinstance(queries.retrieve_porto_dataset_batch(context, 1, None), list)
        assert isinstance(queries.retrieve_porto_dataset_batch(context, 1, ""), list)
        assert isinstance(queries.retrieve_beijing_data_batch(context, 1, None), list)
        assert isinstance(queries.retrieve_beijing_data_batch(context, 1, ""), list)
        assert len(asyncio.run(queries.get_trajectories_from_db(context, name, None, None, None))) == 1
        result = asyncio.run(
            queries.get_trajectories_from_db(
                context, name, now - timedelta(days=1), now + timedelta(days=1), 1
            )
        )
        assert len(result) == 1
        assert isinstance(result[0], UniformedTrajectories)
        assert isinstance(result[0].points[0], UniformedTrajectoryPoint)
    finally:
        context.rollback()
        context.close()


def test_query_errors_are_raised_and_cursors_closed():
    """Ensure query errors propagate after closing their cursors."""
    calls = [
        lambda context: queries.get_dataset_id(context, "x"),
        lambda context: queries.create_source_trajectories(context, 1, ["x"]),
        lambda context: queries.insert_porto_trajectories(context, []),
        lambda context: queries.insert_beijing_dataset(context, []),
        lambda context: queries.retrieve_porto_dataset_batch(context, 1, None),
        lambda context: queries.retrieve_beijing_data_batch(context, 1, None),
        lambda context: asyncio.run(queries.get_trajectories_from_db(context, "x", None, None, None)),
        lambda context: queries.dataset_name_taken(context, "x"),
        lambda context: queries.create_dataset(context, "x"),
        lambda context: asyncio.run(queries.get_trajectories_cities_from_db(context)),
        queries.get_vehicle_type_ids,
    ]

    for call in calls:
        context = MagicMock()
        cursor = context.cursor.return_value
        cursor.execute.side_effect = cursor.executemany.side_effect = RuntimeError("database error")

        with pytest.raises(RuntimeError):
            call(context)

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
        queries.insert_data_uniformed_trajectories(context, [trajectory])

    type_cursor.close.assert_called_once()
    insert_cursor.close.assert_called_once()
