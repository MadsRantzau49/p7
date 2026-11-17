from datetime import UTC, date, datetime, time
from types import SimpleNamespace

import routers.subtrajectory_router as subtrajectory_router
from fastapi.testclient import TestClient
from main import app
from models.bounding_box import BoundingBox
from models.similarity import GPSCoordinate, Pathlet, SupportInterval
from models.subtrajectory import Subtrajectory
from models.uniformed_trajectories import UniformedTrajectoryPoint

client = TestClient(app)

QUERY = {
    "a_longitude": -8.616,
    "a_latitude": 41.14,
    "a_max_longitude": -8.612,
    "a_max_latitude": 41.16,
    "b_longitude": -8.598,
    "b_latitude": 41.14,
    "b_max_longitude": -8.594,
    "b_max_latitude": 41.16,
    "start_date": "2013-07-01",
    "end_date": "2013-07-01",
}


def test_get_subtrajectories(monkeypatch):
    """Every search returns both clustered pathlets and their complete source geometries."""
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
    result = response.json()
    assert result["pathlets"][0]["count"] == 2
    assert result["pathlets"][0]["points"][0]["longitude"] == -8.61
    assert result["pathlets"][0]["support"][0]["end_m"] == 50.0
    assert len(result["trajectories"]) == 1
    assert result["trajectories"][0]["subtrajectory_id"] == 1
    assert result["trajectories"][0]["trajectory_id"] == 7
    assert result["trajectories"][0]["points"][0]["longitude"] == -8.61
    assert received["arguments"] == (
        BoundingBox(-8.616, 41.14, -8.612, 41.16),
        BoundingBox(-8.598, 41.14, -8.594, 41.16),
        date(2013, 7, 1),
        date(2013, 7, 1),
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
        lambda: SimpleNamespace(find_similar_trajectories=lambda *arguments: None),
    )

    response = client.get(
        "/api/subtrajectories/get", params={**QUERY, "start_time": "22:00", "end_time": "02:30"}
    )

    assert response.status_code == 200
    assert response.json() == {"pathlets": [], "trajectories": []}
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
