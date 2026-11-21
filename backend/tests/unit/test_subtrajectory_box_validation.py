import pytest
import routers.subtrajectory_router as subtrajectory_router
from fastapi.testclient import TestClient
from main import app

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


@pytest.mark.parametrize(
    ("parameter", "value"),
    [
        ("a_longitude", -181),
        ("a_max_longitude", 181),
        ("b_latitude", -91),
        ("b_max_latitude", 91),
        ("a_longitude", "nan"),
        ("b_max_longitude", "inf"),
    ],
)
def test_invalid_box_coordinates_are_rejected(monkeypatch, parameter, value):
    """Reject invalid coordinates before invoking either service."""
    monkeypatch.setitem(
        app.dependency_overrides, subtrajectory_router.get_subtrajectory_service, lambda: None
    )
    monkeypatch.setitem(app.dependency_overrides, subtrajectory_router.get_similarity_service, lambda: None)

    response = TestClient(app).get("/api/subtrajectories/get", params={**QUERY, parameter: value})

    assert response.status_code == 422


@pytest.mark.parametrize(
    "parameter", ["a_max_longitude", "a_max_latitude", "b_max_longitude", "b_max_latitude"]
)
def test_both_corners_are_required(monkeypatch, parameter):
    """Require both corners instead of silently searching a fixed-size box."""
    monkeypatch.setitem(
        app.dependency_overrides, subtrajectory_router.get_subtrajectory_service, lambda: None
    )
    monkeypatch.setitem(app.dependency_overrides, subtrajectory_router.get_similarity_service, lambda: None)
    query = {key: value for key, value in QUERY.items() if key != parameter}

    response = TestClient(app).get("/api/subtrajectories/get", params=query)

    assert response.status_code == 422
