"""Exercise the real app's frontend-facing endpoints without MySQL or debug files."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from main import app
from pathlets import main as pipeline

FIXTURE = Path(__file__).parents[1] / "data/trajectories/aalborg_germany.csv"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    """Fail on any artifact write or accidental database access in the API workflow."""
    import database.connection as database

    def forbidden(*args, **kwargs):
        raise AssertionError("frontend clustering must not access a database or write debug/output files")

    monkeypatch.setattr(pipeline, "write_json", forbidden)
    monkeypatch.setattr(database.pooling, "MySQLConnectionPool", forbidden)
    with TestClient(app, raise_server_exceptions=True) as test_client:
        yield test_client


def test_frontend_fixture_preview_to_cluster_workflow(client: TestClient):
    """Preview retains CSV IDs, then clustering returns complete Leaflet-ready source assignments."""
    with FIXTURE.open("rb") as source:
        preview = client.post("/api/trajectories/preview", files={"file": (FIXTURE.name, source, "text/csv")})
    assert preview.status_code == 200, preview.text
    trajectories = preview.json()
    assert len(trajectories) == 8
    assert trajectories[0]["trajectory_id"] == "demo"
    assert trajectories[0]["source_rows"][0] == 2
    assert trajectories[0]["vehicle_type"] == "UNKNOWN"
    assert sum(len(t["points"]) for t in trajectories) == 198
    response = client.post(
        "/api/trajectories/pathlets", json={"trajectories": trajectories, "epsilon_m": 2000}
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["coordinate_order"] == "latitude,longitude"
    assert result["metrics"]["trajectory_count"] == 8
    assert result["metrics"]["coverage_complete"] is True
    assert result["metrics"]["shared_pathlet_count"] > 0
    intervals: dict[str, list[tuple[float, float]]] = {t["trajectory_id"]: [] for t in trajectories}
    for pathlet in result["pathlets"]:
        assert pathlet["count"] == len(set(pathlet["trajectory_ids"])) == len(pathlet["assignments"])
        assert pathlet["max_sspd_m"] <= 2000
        for latitude, longitude in pathlet["coordinates"]:
            assert 54 < latitude < 58 and 7 < longitude < 11
        for assignment in pathlet["assignments"]:
            assert assignment["source_rows"]
            intervals[assignment["trajectory_id"]].append((assignment["start"], assignment["end"]))
    for trajectory in trajectories:
        cursor = 0
        for start, end in sorted(intervals[trajectory["trajectory_id"]]):
            assert start == pytest.approx(cursor)
            cursor = end
        assert cursor == len(trajectory["points"]) - 1
    unfiltered = client.post(
        "/api/trajectories/pathlets",
        json={
            "trajectories": trajectories,
            "epsilon_m": 2000,
            "use_spatial_index": False,
            "use_bounding_box_filter": False,
        },
    )
    assert unfiltered.status_code == 200, unfiltered.text
    exhaustive = unfiltered.json()
    assert exhaustive["pathlets"] == result["pathlets"]
    assert exhaustive["metrics"]["use_bounding_box_filter"] is False
    assert (
        exhaustive["metrics"]["sspd_comparison_count"]
        == exhaustive["metrics"]["possible_cross_trajectory_pair_count"]
    )
    assert exhaustive["metrics"]["sspd_comparison_count"] > result["metrics"]["sspd_comparison_count"]


def _numeric_trajectory(trajectory_id: int | str) -> dict[str, object]:
    return {
        "trajectory_id": trajectory_id,
        "points": [
            {"longitude": 10.0, "latitude": 56.0, "point_timestamp": "2024-01-01T00:00:00"},
            {"longitude": 10.01, "latitude": 56.0, "point_timestamp": "2024-01-01T00:00:10"},
        ],
    }


def test_numeric_database_ids_singletons_and_unrelated_timestamps(client: TestClient):
    """Database IDs survive as stable assignment strings and do not require synchronized timestamps."""
    first, second = _numeric_trajectory(42), _numeric_trajectory(99)
    second["points"] = [
        {"longitude": 10.0, "latitude": 56.0, "point_timestamp": "2025-01-01T00:00:00"},
        {"longitude": 10.01, "latitude": 56.0, "point_timestamp": "2025-01-01T00:01:00"},
    ]
    result = client.post("/api/trajectories/pathlets", json={"trajectories": [first, second], "epsilon_m": 1})
    assert result.status_code == 200
    assert len(result.json()["pathlets"]) == 1
    assert result.json()["pathlets"][0]["trajectory_ids"] == ["42", "99"]
    assert result.json()["metrics"]["use_spatial_index"] is True
    baseline = client.post(
        "/api/trajectories/pathlets",
        json={
            "trajectories": [first, second],
            "epsilon_m": 1,
            "use_spatial_index": False,
        },
    )
    assert baseline.status_code == 200
    assert baseline.json()["pathlets"] == result.json()["pathlets"]
    assert baseline.json()["metrics"]["candidate_search_method"] == "brute_force"
    assert baseline.json()["metrics"]["step_runtime_ms"]["03_spatial_index"] == 0
    assert baseline.json()["metrics"]["possible_cross_trajectory_pair_count"] == 1
    singleton = client.post("/api/trajectories/pathlets", json={"trajectories": [first]})
    assert singleton.status_code == 200
    assert singleton.json()["pathlets"][0]["count"] == 1


@pytest.mark.parametrize(
    "body",
    [
        {"trajectories": []},
        {"trajectories": [_numeric_trajectory(1)], "epsilon_m": -1},
        {"trajectories": [{"trajectory_id": 1, "points": []}]},
        {
            "trajectories": [
                {
                    "trajectory_id": 1,
                    "points": [
                        {"longitude": 181, "latitude": 56, "point_timestamp": "2024-01-01T00:00:00"},
                        {"longitude": 10, "latitude": 56, "point_timestamp": "2024-01-01T00:01:00"},
                    ],
                }
            ]
        },
    ],
)
def test_invalid_clustering_input_has_validation_errors(client: TestClient, body):
    """Invalid distances, coordinates, and missing source portions are rejected before clustering."""
    assert client.post("/api/trajectories/pathlets", json=body).status_code == 422


def test_duplicate_normalized_ids_and_bad_provenance_are_rejected(client: TestClient):
    """Numeric and string IDs cannot silently collapse distinct source trajectories."""
    duplicated = client.post(
        "/api/trajectories/pathlets",
        json={
            "trajectories": [_numeric_trajectory(1), _numeric_trajectory("1")],
        },
    )
    assert duplicated.status_code == 400
    assert "unique" in duplicated.json()["detail"]
    invalid = _numeric_trajectory(1)
    invalid["source_rows"] = [2]
    assert client.post("/api/trajectories/pathlets", json={"trajectories": [invalid]}).status_code == 400


def test_malformed_csv_and_encoding_are_reported(client: TestClient):
    """CSV preview reports actionable errors instead of database or file-system failures."""
    invalid = client.post("/api/trajectories/preview", files={"file": ("bad.csv", b"wrong,header\n1,2\n")})
    assert invalid.status_code == 422
    assert "line 1" in invalid.json()["detail"]
    encoding = client.post("/api/trajectories/preview", files={"file": ("bad.csv", b"\xff\xfe")})
    assert encoding.status_code == 422
    assert "UTF-8" in encoding.json()["detail"]
