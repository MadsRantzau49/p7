import asyncio
from contextlib import contextmanager
from datetime import date, time
from unittest.mock import AsyncMock, MagicMock

import dependencies
import pytest
from services import trajectory_service as service


def setup_service(monkeypatch):
    """Provide a service with mock repositories and connection cleanup."""
    context = MagicMock()
    trajectory_repository = MagicMock()
    dataset_repository = MagicMock()

    trajectory_repository.get_trajectories_from_db = AsyncMock()
    dataset_repository.get_trajectories_cities_from_db = AsyncMock()

    monkeypatch.setattr(dependencies, "create_db_connection", lambda: context)
    monkeypatch.setattr(
        dependencies,
        "get_trajectory_repository",
        lambda connection: trajectory_repository,
    )
    monkeypatch.setattr(
        dependencies,
        "get_dataset_repository",
        lambda connection: dataset_repository,
    )

    return context, trajectory_repository, dataset_repository


def test_get_trajectories_returns_query_result(monkeypatch):
    """Return trajectories and release the connection afterward."""
    context, trajectory_repository, _ = setup_service(monkeypatch)
    result = [{"id": 1}]
    trajectory_repository.get_trajectories_from_db.return_value = result

    with contextmanager(dependencies.get_trajectory_service)() as instance:
        actual = asyncio.run(instance.get_trajectories("Porto", None, None, None, None, 1))

    assert actual == result
    context.close.assert_called_once()


def test_get_trajectories_cities_returns_query_result(monkeypatch):
    """Return cities and release the connection afterward."""
    context, _, dataset_repository = setup_service(monkeypatch)
    result = [{"name": "Porto"}]
    dataset_repository.get_trajectories_cities_from_db.return_value = result

    with contextmanager(dependencies.get_trajectory_service)() as instance:
        actual = asyncio.run(instance.get_trajectories_cities())

    assert actual == result
    context.close.assert_called_once()


def test_get_trajectories_closes_connection_after_query_error(monkeypatch):
    """Close the connection when the trajectory query fails."""
    context, trajectory_repository, _ = setup_service(monkeypatch)
    trajectory_repository.get_trajectories_from_db.side_effect = RuntimeError("failed")

    with pytest.raises(RuntimeError):
        with contextmanager(dependencies.get_trajectory_service)() as instance:
            asyncio.run(instance.get_trajectories("Porto", None, None, None, None, 1))

    context.close.assert_called_once()


def test_get_trajectories_cities_closes_connection_after_query_error(monkeypatch):
    """Close the connection when the city query fails."""
    context, _, dataset_repository = setup_service(monkeypatch)
    dataset_repository.get_trajectories_cities_from_db.side_effect = RuntimeError("failed")

    with pytest.raises(RuntimeError):
        with contextmanager(dependencies.get_trajectory_service)() as instance:
            asyncio.run(instance.get_trajectories_cities())

    context.close.assert_called_once()


def test_trajectory_service_ignores_full_day_time_range(monkeypatch):
    """Treat the complete day as no time filter and release the connection."""
    context, trajectory_repository, _ = setup_service(monkeypatch)
    query = trajectory_repository.get_trajectories_from_db
    query.return_value = []

    with contextmanager(dependencies.get_trajectory_service)() as instance:
        asyncio.run(instance.get_trajectories("Porto", None, None, time.min, time(23, 59), 1))

    query.assert_awaited_once_with("Porto", None, None, None, None, 1)
    context.close.assert_called_once()


@pytest.mark.parametrize(
    ("start_date", "end_date", "start_time", "end_time"),
    [
        (date(2024, 2, 1), date(2024, 1, 1), None, None),
        (date(2024, 1, 1), date(2024, 1, 1), time(2), time(1)),
    ],
)
def test_trajectory_service_rejects_invalid_ranges(
    start_date: date,
    end_date: date,
    start_time: time | None,
    end_time: time | None,
):
    """Reject reversed date and same-day time ranges."""
    instance = service.TrajectoryService(
        trajectory_repository=MagicMock(),
        dataset_repository=MagicMock(),
    )

    with pytest.raises(ValueError):
        asyncio.run(instance.get_trajectories("Porto", start_date, end_date, start_time, end_time, None))
