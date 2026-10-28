from types import SimpleNamespace

import routers.dataset_router as dataset_router
from fastapi.testclient import TestClient
from helpers.trajectory_csv_parser import InvalidTrajectoryCsvError
from helpers.upload_parser import UploadError
from main import app
from services.dataset_upload_service import (
    CityTimeZoneMismatchError,
    DatasetNameTakenError,
    InvalidTimeZoneError,
)

client = TestClient(app)
FORM = {"name": "Porto", "city": "Porto", "time_zone": "Europe/Lisbon"}


def test_upload_dataset_success(monkeypatch):
    """Check a valid dataset upload returns 201."""

    def upload_dataset(name, city, time_zone, lines):
        return 42

    def override_dataset_upload_service():
        return SimpleNamespace(upload_dataset=upload_dataset)

    monkeypatch.setitem(
        app.dependency_overrides,
        dataset_router.get_dataset_upload_service,
        override_dataset_upload_service,
    )

    response = client.post(
        "/api/datasets/upload",
        data={**FORM},
        files={"file": ("data.csv", b"some csv data", "text/csv")},
    )

    assert response.status_code == 201
    assert response.json() == {
        "dataset_id": 42,
        "name": "Porto",
        "city": "Porto",
    }


def test_upload_dataset_name_is_stripped(monkeypatch):
    """Check whitespace is removed from the dataset name."""
    received = {}

    def upload_dataset(name, city, time_zone, lines):
        received["name"] = name
        received["city"] = city
        return 42

    def override_dataset_upload_service():
        return SimpleNamespace(upload_dataset=upload_dataset)

    monkeypatch.setitem(
        app.dependency_overrides,
        dataset_router.get_dataset_upload_service,
        override_dataset_upload_service,
    )

    response = client.post(
        "/api/datasets/upload",
        data={**FORM, "name": "  Porto ", "city": "   Porto"},
        files={"file": ("data.csv", b"some csv data", "text/csv")},
    )

    assert response.status_code == 201
    assert received["name"] == "Porto"
    assert received["city"] == "Porto"
    assert response.json()["name"] == "Porto"


def test_upload_dataset_too_large(monkeypatch):
    """Check files larger than the limit return 413."""
    monkeypatch.setattr(dataset_router, "MAX_UPLOAD_BYTES", 1)
    monkeypatch.setitem(
        app.dependency_overrides,
        dataset_router.get_dataset_upload_service,
        lambda: SimpleNamespace(),
    )

    response = client.post(
        "/api/datasets/upload",
        data={**FORM},
        files={"file": ("data.csv", b"12", "text/csv")},
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "file is larger than 0 MB"


def test_upload_dataset_invalid_csv(monkeypatch):
    """Check invalid CSV data returns 422."""

    def upload_invalid_dataset(name, city, time_zone, lines):
        raise InvalidTrajectoryCsvError(
            [
                UploadError(
                    2,
                    "invalid trajectory",
                )
            ]
        )

    def override_invalid_dataset_upload_service():
        return SimpleNamespace(upload_dataset=upload_invalid_dataset)

    monkeypatch.setitem(
        app.dependency_overrides,
        dataset_router.get_dataset_upload_service,
        override_invalid_dataset_upload_service,
    )

    response = client.post(
        "/api/datasets/upload",
        data={**FORM},
        files={"file": ("data.csv", b"invalid", "text/csv")},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == [
        {
            "line": 2,
            "message": "invalid trajectory",
        }
    ]


def test_upload_dataset_name_taken(monkeypatch):
    """Check duplicate dataset names return 409."""

    def upload_dataset_with_taken_name(name, city, time_zone, lines):
        raise DatasetNameTakenError()

    def override_taken_dataset_upload_service():
        return SimpleNamespace(upload_dataset=upload_dataset_with_taken_name)

    monkeypatch.setitem(
        app.dependency_overrides,
        dataset_router.get_dataset_upload_service,
        override_taken_dataset_upload_service,
    )

    response = client.post(
        "/api/datasets/upload",
        data={**FORM},
        files={"file": ("data.csv", b"data", "text/csv")},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "a dataset named 'Porto' already exists"


def test_upload_dataset_invalid_encoding(monkeypatch):
    """Check invalid UTF-8 input returns 422."""

    def upload_dataset_with_invalid_encoding(name, city, time_zone, lines):
        raise UnicodeDecodeError(
            "utf-8",
            b"\xff",
            0,
            1,
            "invalid start byte",
        )

    def override_upload_dataset_with_invalid_encoding():
        return SimpleNamespace(upload_dataset=upload_dataset_with_invalid_encoding)

    monkeypatch.setitem(
        app.dependency_overrides,
        dataset_router.get_dataset_upload_service,
        override_upload_dataset_with_invalid_encoding,
    )

    response = client.post(
        "/api/datasets/upload",
        data={**FORM},
        files={"file": ("data.csv", b"data", "text/csv")},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "file must be UTF-8 encoded"


def test_upload_dataset_invalid_time_zone(monkeypatch):
    """Check an unknown time zone returns 422."""

    def upload_dataset_with_invalid_time_zone(name, city, time_zone, lines):
        raise InvalidTimeZoneError(time_zone)

    def override_invalid_time_zone_upload_service():
        return SimpleNamespace(upload_dataset=upload_dataset_with_invalid_time_zone)

    monkeypatch.setitem(
        app.dependency_overrides,
        dataset_router.get_dataset_upload_service,
        override_invalid_time_zone_upload_service,
    )

    response = client.post(
        "/api/datasets/upload",
        data={**FORM, "time_zone": "Asia/Calcutta"},
        files={"file": ("data.csv", b"data", "text/csv")},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "unknown time zone 'Asia/Calcutta'"


def test_upload_dataset_city_time_zone_mismatch(monkeypatch):
    """Check a time zone that differs from the existing city's returns 409."""

    def upload_dataset_with_other_time_zone(name, city, time_zone, lines):
        raise CityTimeZoneMismatchError(city, "Europe/Lisbon")

    def override_mismatch_upload_service():
        return SimpleNamespace(upload_dataset=upload_dataset_with_other_time_zone)

    monkeypatch.setitem(
        app.dependency_overrides,
        dataset_router.get_dataset_upload_service,
        override_mismatch_upload_service,
    )

    response = client.post(
        "/api/datasets/upload",
        data={**FORM, "time_zone": "Europe/London"},
        files={"file": ("data.csv", b"data", "text/csv")},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "the city 'Porto' already uses the time zone 'Europe/Lisbon'"


def get_time_zones(monkeypatch):
    """Check the time zone list is returned."""

    def override_time_zone_service():
        return SimpleNamespace(get_time_zones=lambda: ["Europe/Copenhagen", "Europe/Lisbon"])

    monkeypatch.setitem(
        app.dependency_overrides,
        dataset_router.get_dataset_upload_service,
        override_time_zone_service,
    )

    response = client.get("/api/datasets/time-zones")

    assert response.status_code == 200
    assert response.json() == ["Europe/Copenhagen", "Europe/Lisbon"]
