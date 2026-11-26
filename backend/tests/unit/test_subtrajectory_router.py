import logging
import re
from contextlib import nullcontext
from datetime import UTC, date, datetime, time
from types import SimpleNamespace
from unittest.mock import MagicMock

import dependencies
import routers.router as router
from fastapi.testclient import TestClient
from main import app
from models.bounding_box import BoundingBox
from models.date_range import DateRange
from models.similarity import GPSCoordinate, Route
from models.subtrajectory import Subtrajectory
from models.uniformed_trajectories import UniformedTrajectoryPoint

client = TestClient(app)

QUERY = {
    "a_longitude": -8.614,
    "a_latitude": 41.15,
    "a_max_longitude": -8.612,
    "a_max_latitude": 41.16,
    "b_longitude": -8.596,
    "b_latitude": 41.15,
    "b_max_longitude": -8.594,
    "b_max_latitude": 41.16,
    "start_date": "2013-07-01",
    "end_date": "2013-07-01",
}


def test_get_subtrajectories(monkeypatch):
    """Check the found subtrajectories go through the clustering service and routes are returned as JSON."""
    received = {}
    moment = datetime(2013, 7, 1, 8, 10, tzinfo=UTC)
    subtrajectories = [Subtrajectory(1, 7, moment, moment, [UniformedTrajectoryPoint(-8.61, moment, 41.15)])]

    def find_subtrajectories(*arguments):
        received["arguments"] = arguments
        return subtrajectories

    def find_routes(*arguments):
        received["clustering_arguments"] = arguments
        return [Route([GPSCoordinate(41.15, -8.61)], 2)]

    monkeypatch.setitem(
        app.dependency_overrides,
        router.get_subtrajectory_service,
        lambda: SimpleNamespace(find_subtrajectories=find_subtrajectories),
    )
    monkeypatch.setitem(
        app.dependency_overrides,
        router.get_route_clustering_service,
        lambda: SimpleNamespace(find_routes=find_routes),
    )

    response = client.get("/api/subtrajectories/get", params=QUERY)

    assert response.status_code == 200
    assert response.json()[0]["count"] == 2
    assert response.json()[0]["points"][0]["longitude"] == -8.61
    assert "support" not in response.json()[0]
    assert received["arguments"] == (
        BoundingBox(-8.614, 41.15, -8.612, 41.16),
        BoundingBox(-8.596, 41.15, -8.594, 41.16),
        DateRange(date(2013, 7, 1), date(2013, 7, 1)),
        None,
        None,
    )
    assert received["clustering_arguments"] == (subtrajectories, 100)


def test_get_subtrajectories_passes_time_window(monkeypatch):
    """Check start_time and end_time are parsed and passed to the service."""
    received = {}

    def find_subtrajectories(*arguments):
        received["arguments"] = arguments
        return []

    monkeypatch.setitem(
        app.dependency_overrides,
        router.get_subtrajectory_service,
        lambda: SimpleNamespace(find_subtrajectories=find_subtrajectories),
    )
    monkeypatch.setitem(
        app.dependency_overrides,
        router.get_route_clustering_service,
        lambda: SimpleNamespace(find_routes=lambda *arguments: []),
    )

    response = client.get(
        "/api/subtrajectories/get", params={**QUERY, "start_time": "22:00", "end_time": "02:30"}
    )

    assert response.status_code == 200
    assert received["arguments"][-2:] == (time(22, 0), time(2, 30))


def test_find_routes_logs_pipeline_timings(monkeypatch, caplog):
    """Time the real route-finding services using a fake database connection."""
    connection = MagicMock()
    connection.cursor.return_value.fetchall.return_value = [
        {
            "trajectory_id": 7,
            "time_zone": "Europe/Lisbon",
            "exit_a_time": datetime(2013, 7, 1, 8, 10, tzinfo=UTC),
            "entry_b_time": datetime(2013, 7, 1, 8, 12, tzinfo=UTC),
            "exit_a_longitude": -8.612,
            "exit_a_latitude": 41.15,
            "entry_b_longitude": -8.596,
            "entry_b_latitude": 41.15,
            "points": [],
        }
    ]
    monkeypatch.setattr(dependencies, "create_db_connection", lambda: nullcontext(connection))

    with caplog.at_level(logging.INFO):
        response = client.get("/api/subtrajectories/get", params=QUERY)

    assert response.status_code == 200
    loggers = {
        "FindRoutes",
        "DatabaseConnection",
        "SubtrajectoryService",
        "TrajectoryRepository",
        "ClusteringService",
    }
    messages = [record.getMessage() for record in caplog.records if record.name in loggers]
    assert all(
        message.startswith("=== ") or re.fullmatch(r".+ took \d+\.\d{3} seconds", message)
        for message in messages
    )
    messages = [message.split(" took ")[0] for message in messages]
    assert messages == [
        "=== Find routes ===",
        "=== Database connection ===",
        "Acquire pooled connection",
        "=== SubtrajectoryService ===",
        "Validate query",
        "=== TrajectoryRepository ===",
        "Execute SQL and receive results",
        "Fetch and decode rows",
        "Build subtrajectories",
        "=== ClusteringService ===",
        "Step 1: Projection",
        "Step 2: Build polylines",
        "Step 3: Assign clusters",
        "Step 4: Choose representatives",
        "Step 5: Build routes",
        "Step 6: Inverse projection",
        "Clustering total",
        "Find routes request",
    ]


def test_get_cluster_subtrajectories(monkeypatch):
    """Clicking a cluster re-extracts the subtrajectories and returns only its members."""
    moment = datetime(2013, 7, 1, 8, 10, tzinfo=UTC)
    other = datetime(2013, 7, 1, 9, 0, tzinfo=UTC)
    subtrajectories = [
        Subtrajectory(1, 7, moment, moment, [UniformedTrajectoryPoint(-8.61, moment, 41.15)]),
        Subtrajectory(2, 9, other, other, [UniformedTrajectoryPoint(-8.62, other, 41.16)]),
    ]

    monkeypatch.setitem(
        app.dependency_overrides,
        router.get_subtrajectory_service,
        lambda: SimpleNamespace(find_subtrajectories=lambda *arguments: subtrajectories),
    )

    body = {
        **QUERY,
        "members": [
            {
                "trajectory_id": 7,
                "exit_a_time": moment.isoformat(),
                "entry_b_time": moment.isoformat(),
            }
        ],
    }

    response = client.post("/api/subtrajectories/cluster", json=body)

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["trajectory_id"] == 7
    assert data[0]["points"][0]["longitude"] == -8.61
    assert data[0]["points"][0]["latitude"] == 41.15


def test_get_subtrajectories_invalid_input(monkeypatch):
    """Check a ValueError from the service returns 400."""

    def find_subtrajectories(*arguments):
        raise ValueError("box A and box B must not overlap")

    monkeypatch.setitem(
        app.dependency_overrides,
        router.get_subtrajectory_service,
        lambda: SimpleNamespace(find_subtrajectories=find_subtrajectories),
    )

    response = client.get("/api/subtrajectories/get", params=QUERY)

    assert response.status_code == 400
    assert response.json()["detail"] == "box A and box B must not overlap"
