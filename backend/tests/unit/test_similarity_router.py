from pathlib import Path
from unittest.mock import MagicMock

import routers.similarity_router as similarity_router
from fastapi import FastAPI
from fastapi.testclient import TestClient
from services.similarity_service import SimilarityService

app = FastAPI()
app.include_router(similarity_router.router)
client = TestClient(app)

CSV = (
    "trajectory_id,vehicle_id,vehicle_type,timestamp,longitude,latitude,city,source_id,database_trajectory_id\n"
    "route,0,CAR,2026-01-01 12:00:00,9,57,,,42\n"
    "route,0,CAR,2026-01-01 12:00:15,9.001,57.001,,,42\n"
)


def test_csv_upload_runs_the_complete_fds_pipeline():
    """Return map-ready pathlets using the same fixture as the debug run."""
    fixture = Path(__file__).parent.parent / "data/trajectories/skagen_to_aalborg.csv"
    with fixture.open("rb") as file:
        response = client.post(
            "/api/similarity/fds",
            data={"epsilon": "2000", "max_entries": "4"},
            files={"file": (fixture.name, file, "text/csv")},
        )

    assert response.status_code == 200
    pathlets = response.json()
    assert len(pathlets) == 48
    assert set(pathlets[0]) == {"pathlet_id", "count", "trajectories_included", "points"}
    assert set(pathlets[0]["points"][0]) == {"latitude", "longitude"}
    trajectory_ids = {
        trajectory_id for pathlet in pathlets for trajectory_id in pathlet["trajectories_included"]
    }
    assert trajectory_ids == set(range(888, 898))
    for pathlet in pathlets:
        assert pathlet["count"] == len(pathlet["trajectories_included"])
        assert len(pathlet["points"]) >= 2


def test_csv_upload_passes_the_arguments_and_subpaths_to_fds(monkeypatch):
    """Forward user settings and preserve explicit trajectory IDs from the CSV."""
    service = MagicMock(spec=SimilarityService)
    service.FDS.return_value = []
    monkeypatch.setattr(similarity_router, "SimilarityService", lambda: service)

    response = client.post(
        "/api/similarity/fds",
        data={"epsilon": "12.5", "max_entries": "8"},
        files={"file": ("routes.csv", CSV.encode("utf-8-sig"), "text/csv")},
    )

    assert response.status_code == 200
    service.FDS.assert_called_once()
    subpaths, epsilon, max_entries = service.FDS.call_args.args
    assert epsilon == 12.5
    assert max_entries == 8
    assert len(subpaths) == 1
    assert subpaths[0].trajectory_id == 42
    assert len(subpaths[0].points) == 2
    assert subpaths[0].exit_a_time == subpaths[0].points[0].point_timestamp
    assert subpaths[0].entry_b_time == subpaths[0].points[-1].point_timestamp


def test_invalid_csv_headers_return_line_details():
    """Expose parser errors so the UI can explain which CSV line failed."""
    response = client.post(
        "/api/similarity/fds", files={"file": ("bad.csv", b"wrong,header\n", "text/csv")}
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["line"] == 1
    assert "header must be exactly" in response.json()["detail"][0]["message"]


def test_invalid_vehicle_types_return_each_line_error():
    """Show the enum names required when a database export contains numeric types."""
    response = client.post(
        "/api/similarity/fds",
        files={"file": ("bad.csv", CSV.replace(",CAR,", ",2,").encode(), "text/csv")},
    )

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert [error["line"] for error in errors] == [2, 3]
    assert all("vehicle_type" in error["message"] for error in errors)


def test_negative_epsilon_is_rejected():
    """Validate a non-negative distance before running FDS."""
    response = client.post(
        "/api/similarity/fds",
        data={"epsilon": "-1"},
        files={"file": ("routes.csv", CSV.encode(), "text/csv")},
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "epsilon"]


def test_nonfinite_epsilon_is_rejected():
    """An infinite threshold cannot be used to build expanded boxes."""
    response = client.post(
        "/api/similarity/fds",
        data={"epsilon": "inf"},
        files={"file": ("routes.csv", CSV.encode(), "text/csv")},
    )

    assert response.status_code == 422


def test_rtree_capacity_below_two_is_rejected():
    """Validate the tree capacity before running FDS."""
    response = client.post(
        "/api/similarity/fds",
        data={"max_entries": "1"},
        files={"file": ("routes.csv", CSV.encode(), "text/csv")},
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "max_entries"]


def test_non_utf8_upload_is_rejected():
    """Report a readable encoding error instead of a server error."""
    response = client.post(
        "/api/similarity/fds", files={"file": ("bad.csv", b"\xff", "text/csv")}
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "file must be UTF-8 encoded"


def test_oversized_upload_is_rejected(monkeypatch):
    """Apply the upload limit before parsing the file."""
    monkeypatch.setattr(similarity_router, "MAX_UPLOAD_BYTES", 1)

    response = client.post(
        "/api/similarity/fds", files={"file": ("routes.csv", CSV.encode(), "text/csv")}
    )

    assert response.status_code == 413
