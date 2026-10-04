import routers.trajectory_router as trajectory_router
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_get_trajectories(monkeypatch):
    """Check trajectory endpoint returns service result."""

    async def fake_get_trajectories(city, start_date, end_date, start_time, end_time, limit):
        return [{"trajectory_id": 1, "city": city}]

    monkeypatch.setattr(
        trajectory_router,
        "get_trajectories",
        fake_get_trajectories,
    )

    response = client.get(
        "/api/trajectories/get",
        params={
            "city": "Porto",
            "start_date": "2024-01-01",
            "end_date": "2024-02-01",
            "start_time": "08:00:00",
            "end_time": "16:00:00",
            "limit": 10,
        },
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "trajectory_id": 1,
            "city": "Porto",
        }
    ]


def test_get_trajectories_rejects_invalid_range(monkeypatch):
    """Return 400 when trajectory filters are invalid."""

    async def fake_get_trajectories(*args):
        raise ValueError("invalid range")

    monkeypatch.setattr(trajectory_router, "get_trajectories", fake_get_trajectories)

    response = client.get("/api/trajectories/get", params={"city": "Porto"})

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid range"


def test_get_trajectory_cities(monkeypatch):
    """Check cities endpoint returns service result."""

    async def fake_get_trajectories_cities():
        return [
            {"dataset_id": 1, "name": "Porto"},
            {"dataset_id": 2, "name": "Beijing"},
        ]

    monkeypatch.setattr(
        trajectory_router,
        "get_trajectories_cities",
        fake_get_trajectories_cities,
    )

    response = client.get("/api/trajectories/get/cities")

    assert response.status_code == 200
    assert response.json() == [
        {"dataset_id": 1, "name": "Porto"},
        {"dataset_id": 2, "name": "Beijing"},
    ]
