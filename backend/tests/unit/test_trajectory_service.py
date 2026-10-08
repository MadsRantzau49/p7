import asyncio
from datetime import date, time
from unittest.mock import AsyncMock, MagicMock

import pytest
from services import trajectory_service as service


@pytest.mark.parametrize(
    ("function_name", "query_name", "arguments", "result"),
    [
        (
            "get_trajectories",
            "get_trajectories_from_db",
            ("Porto", None, None, None, None, 1),
            [{"id": 1}],
        ),
        ("get_trajectories_cities", "get_trajectories_cities_from_db", (), [{"name": "Porto"}]),
    ],
)
def test_trajectory_service(monkeypatch, function_name, query_name, arguments, result):
    """Return query results and always close the database connection."""
    context = MagicMock()
    monkeypatch.setattr(service, "create_db_connection", lambda: context)
    monkeypatch.setattr(service, query_name, AsyncMock(return_value=result))

    assert asyncio.run(getattr(service, function_name)(*arguments)) == result
    context.close.assert_called_once()


@pytest.mark.parametrize(
    ("function_name", "query_name", "arguments"),
    [
        ("get_trajectories", "get_trajectories_from_db", ("Porto", None, None, None, None, 1)),
        ("get_trajectories_cities", "get_trajectories_cities_from_db", ()),
    ],
)
def test_trajectory_service_error(monkeypatch, function_name, query_name, arguments):
    """Propagate query errors and always close the database connection."""
    context = MagicMock()
    monkeypatch.setattr(service, "create_db_connection", lambda: context)
    monkeypatch.setattr(service, query_name, AsyncMock(side_effect=RuntimeError("failed")))

    with pytest.raises(RuntimeError):
        asyncio.run(getattr(service, function_name)(*arguments))

    context.close.assert_called_once()


def test_trajectory_service_ignores_full_day_time_range(monkeypatch):
    """Treat the complete day as no time filter."""
    context = MagicMock()
    query = AsyncMock(return_value=[])
    monkeypatch.setattr(service, "create_db_connection", lambda: context)
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
