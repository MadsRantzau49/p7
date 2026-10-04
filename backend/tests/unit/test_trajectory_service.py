import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from services import trajectory_service as service


@pytest.mark.parametrize(
    ("function_name", "query_name", "arguments", "result"),
    [
        ("get_trajectories", "get_trajectories_from_db", ("Porto", None, None, 1), [{"id": 1}]),
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
        ("get_trajectories", "get_trajectories_from_db", ("Porto", None, None, 1)),
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
