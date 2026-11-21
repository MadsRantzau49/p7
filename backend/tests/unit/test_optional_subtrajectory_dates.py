from datetime import UTC, date, datetime, time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import routers.subtrajectory_router as subtrajectory_router
from fastapi.testclient import TestClient
from main import app
from services.subtrajectory_service import SubtrajectoryService

# Supplying both corners also exercises these tests when combined with box selection.
QUERY = {
    "a_longitude": -8.616,
    "a_latitude": 41.14,
    "a_max_longitude": -8.612,
    "a_max_latitude": 41.16,
    "b_longitude": -8.598,
    "b_latitude": 41.14,
    "b_max_longitude": -8.594,
    "b_max_latitude": 41.16,
}


@pytest.fixture
def search(monkeypatch):
    """Use the real date filtering with a repository row crossing a local date boundary."""
    repository = MagicMock()
    repository.get_subtrajectories.return_value = [
        {
            "trajectory_id": 7,
            "exit_a_time": datetime(2013, 7, 1, 23, 30, tzinfo=UTC),
            "entry_b_time": datetime(2013, 7, 1, 23, 35, tzinfo=UTC),
            "exit_a_longitude": -8.612,
            "exit_a_latitude": 41.15,
            "entry_b_longitude": -8.598,
            "entry_b_latitude": 41.15,
            "points": [],
            "time_zone": "Europe/Lisbon",
        }
    ]
    similarity = MagicMock(return_value=[])
    monkeypatch.setitem(
        app.dependency_overrides,
        subtrajectory_router.get_subtrajectory_service,
        lambda: SubtrajectoryService(repository),
    )
    monkeypatch.setitem(
        app.dependency_overrides,
        subtrajectory_router.get_similarity_service,
        lambda: SimpleNamespace(find_similar_trajectories=similarity),
    )
    return TestClient(app), repository, similarity


@pytest.mark.parametrize(
    ("bounds", "expected_count"),
    [
        ({}, 1),
        ({"start_date": "2013-07-02"}, 1),
        ({"end_date": "2013-07-02"}, 1),
        ({"start_date": "2013-07-03"}, 0),
        ({"end_date": "2013-07-01"}, 0),
        ({"start_date": "2013-07-02", "end_date": "2013-07-02"}, 1),
    ],
)
def test_optional_date_bounds_use_local_departure_date(search, bounds, expected_count):
    """Apply each provided date bound inclusively in the city's time zone."""
    client, repository, similarity = search

    response = client.get("/api/subtrajectories/get", params={**QUERY, **bounds})

    assert response.status_code == 200
    assert len(similarity.call_args.args[0]) == expected_count
    assert repository.get_subtrajectories.call_args.args[-4:-2] == tuple(
        date.fromisoformat(bounds[key]) if key in bounds else None for key in ("start_date", "end_date")
    )


def test_time_window_without_dates(search):
    """Keep passing the overnight daily window when both date bounds are omitted."""
    client, repository, _ = search

    response = client.get(
        "/api/subtrajectories/get", params={**QUERY, "start_time": "22:00", "end_time": "02:00"}
    )

    assert response.status_code == 200
    assert repository.get_subtrajectories.call_args.args[-4:] == (None, None, time(22), time(2))


def test_reversed_date_range_is_rejected(search):
    """Reject reversed bounds before accessing the repository."""
    client, repository, _ = search

    response = client.get(
        "/api/subtrajectories/get", params={**QUERY, "start_date": "2013-07-03", "end_date": "2013-07-01"}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "start_date must be on or before end_date"
    repository.get_subtrajectories.assert_not_called()
