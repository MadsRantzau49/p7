import asyncio
from datetime import date, time
from unittest.mock import AsyncMock, MagicMock

import pytest
from services import trajectory_service as service


def setup_database_connection(monkeypatch):
    """Use and return a test database connection."""
    context = MagicMock()

    def create_db_connection():
        return context

    monkeypatch.setattr(service, "create_db_connection", create_db_connection)
    return context


def test_get_trajectories_returns_query_result(monkeypatch):
    """Return trajectories from the database query."""
    context = setup_database_connection(monkeypatch)
    result = [{"id": 1}]
    monkeypatch.setattr(service, "get_trajectories_from_db", AsyncMock(return_value=result))

    actual = asyncio.run(service.get_trajectories("Porto", None, None, None, None, 1))

    assert actual == result
    context.close.assert_called_once()


def test_get_trajectories_cities_returns_query_result(monkeypatch):
    """Return cities from the database query."""
    context = setup_database_connection(monkeypatch)
    result = [{"name": "Porto"}]
    monkeypatch.setattr(service, "get_trajectories_cities_from_db", AsyncMock(return_value=result))

    actual = asyncio.run(service.get_trajectories_cities())

    assert actual == result
    context.close.assert_called_once()


def test_get_trajectories_closes_connection_after_query_error(monkeypatch):
    """Close the database connection when the trajectory query fails."""
    context = setup_database_connection(monkeypatch)
    monkeypatch.setattr(
        service,
        "get_trajectories_from_db",
        AsyncMock(side_effect=RuntimeError("failed")),
    )

    with pytest.raises(RuntimeError):
        asyncio.run(service.get_trajectories("Porto", None, None, None, None, 1))

    context.close.assert_called_once()


def test_get_trajectories_cities_closes_connection_after_query_error(monkeypatch):
    """Close the database connection when the city query fails."""
    context = setup_database_connection(monkeypatch)
    monkeypatch.setattr(
        service,
        "get_trajectories_cities_from_db",
        AsyncMock(side_effect=RuntimeError("failed")),
    )

    with pytest.raises(RuntimeError):
        asyncio.run(service.get_trajectories_cities())

    context.close.assert_called_once()


def test_trajectory_service_ignores_full_day_time_range(monkeypatch):
    """Treat the complete day as no time filter."""
    context = setup_database_connection(monkeypatch)
    query = AsyncMock(return_value=[])
    monkeypatch.setattr(service, "get_trajectories_from_db", query)

    asyncio.run(service.get_trajectories("Porto", None, None, time.min, time(23, 59), 1))

    query.assert_awaited_once_with(context, "Porto", None, None, None, None, 1)
    context.close.assert_called_once()


@pytest.mark.parametrize(
    ("start_date", "end_date", "start_time", "end_time"),
    [
        (date(2024, 2, 1), date(2024, 1, 1), None, None),
        (date(2024, 1, 1), date(2024, 1, 1), time(2), time(1)),
    ],
)
def test_trajectory_service_rejects_invalid_ranges(
    start_date: date, end_date: date, start_time: time | None, end_time: time | None
):
    """Reject reversed date and same-day time ranges."""
    with pytest.raises(ValueError):
        asyncio.run(service.get_trajectories("Porto", start_date, end_date, start_time, end_time, None))
