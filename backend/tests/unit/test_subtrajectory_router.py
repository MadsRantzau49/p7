from datetime import UTC, date, datetime
from types import SimpleNamespace

import routers.subtrajectory_router as subtrajectory_router
from fastapi.testclient import TestClient
from main import app
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
    """Check the found subtrajectories are returned as JSON."""
    received = {}
    moment = datetime(2013, 7, 1, 8, 10, tzinfo=UTC)

    def find_subtrajectories(*arguments):
        received["arguments"] = arguments
        return [Subtrajectory(1, 7, moment, moment, [UniformedTrajectoryPoint(-8.61, moment, 41.15)])]

    monkeypatch.setitem(
        app.dependency_overrides,
        subtrajectory_router.get_subtrajectory_service,
        lambda: SimpleNamespace(find_subtrajectories=find_subtrajectories),
    )

    response = client.get("/api/subtrajectories/get", params=QUERY)

    assert response.status_code == 200
    assert response.json()[0]["subtrajectory_id"] == 1
    assert response.json()[0]["points"][0]["longitude"] == -8.61
    assert received["arguments"] == (-8.614, 41.15, -8.596, 41.15, date(2013, 7, 1), date(2013, 7, 1), 50)


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
