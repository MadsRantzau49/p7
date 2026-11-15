from datetime import UTC, date, datetime, time
from types import SimpleNamespace

import routers.subtrajectory_router as subtrajectory_router
from fastapi.testclient import TestClient
from main import app
from models.similarity import GPSCoordinate, Pathlet, SupportInterval
from models.subtrajectory import Subtrajectory
from models.uniformed_trajectories import UniformedTrajectoryPoint

client = TestClient(app)

QUERY = {
    "a_longitude": -8.614,
    "a_latitude": 41.15,
    "b_longitude": -8.596,
    "b_latitude": 41.15,
    "start_date": "2013-07-01",
    "end_date": "2013-07-01",
}


def test_get_subtrajectories(monkeypatch):
    """Check the found subtrajectories go through the similarity service and pathlets are returned as JSON."""
    received = {}
    moment = datetime(2013, 7, 1, 8, 10, tzinfo=UTC)
    subtrajectories = [Subtrajectory(1, 7, moment, moment, [UniformedTrajectoryPoint(-8.61, moment, 41.15)])]

    def find_subtrajectories(*arguments):
        received["arguments"] = arguments
        return subtrajectories

    def find_similar_trajectories(*arguments):
        received["similarity_arguments"] = arguments
        return [Pathlet([GPSCoordinate(41.15, -8.61)], 2, [SupportInterval(0.0, 50.0, 2)])]

    monkeypatch.setitem(
        app.dependency_overrides,
        subtrajectory_router.get_subtrajectory_service,
        lambda: SimpleNamespace(find_subtrajectories=find_subtrajectories),
    )
    monkeypatch.setitem(
        app.dependency_overrides,
        subtrajectory_router.get_similarity_service,
        lambda: SimpleNamespace(find_similar_trajectories=find_similar_trajectories),
    )

    response = client.get("/api/subtrajectories/get", params=QUERY)

    assert response.status_code == 200
    assert response.json()[0]["count"] == 2
    assert response.json()[0]["points"][0]["longitude"] == -8.61
    assert response.json()[0]["support"][0]["end_m"] == 50.0
    assert received["arguments"] == (
        -8.614,
        41.15,
        -8.596,
        41.15,
        date(2013, 7, 1),
        date(2013, 7, 1),
        50,
        None,
        None,
    )
    assert received["similarity_arguments"] == (subtrajectories, 100)


def test_get_subtrajectories_passes_time_window(monkeypatch):
    """Check start_time and end_time are parsed and passed to the service."""
    received = {}

    def find_subtrajectories(*arguments):
        received["arguments"] = arguments
        return []

    monkeypatch.setitem(
        app.dependency_overrides,
        subtrajectory_router.get_subtrajectory_service,
        lambda: SimpleNamespace(find_subtrajectories=find_subtrajectories),
    )
    monkeypatch.setitem(
        app.dependency_overrides,
        subtrajectory_router.get_similarity_service,
        lambda: SimpleNamespace(find_similar_trajectories=lambda *arguments: []),
    )

    response = client.get(
        "/api/subtrajectories/get", params={**QUERY, "start_time": "22:00", "end_time": "02:30"}
    )

    assert response.status_code == 200
    assert received["arguments"][-2:] == (time(22, 0), time(2, 30))


def test_get_subtrajectories_invalid_input(monkeypatch):
    """Check a ValueError from the service returns 400."""

    def find_subtrajectories(*arguments):
        raise ValueError("box A and box B must not overlap")

    monkeypatch.setitem(
        app.dependency_overrides,
        subtrajectory_router.get_subtrajectory_service,
        lambda: SimpleNamespace(find_subtrajectories=find_subtrajectories),
    )

    response = client.get("/api/subtrajectories/get", params=QUERY)

    assert response.status_code == 400
    assert response.json()["detail"] == "box A and box B must not overlap"
