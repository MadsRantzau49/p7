import routers.dataset_router as dataset_router
from fastapi.testclient import TestClient
from helpers.trajectory_csv_parser import InvalidTrajectoryCsvError
from helpers.upload_parser import UploadError
from main import app
from services.dataset_upload_service import DatasetNameTakenError

client = TestClient(app)


def test_upload_dataset_success(monkeypatch):
    """Check a valid dataset upload returns 201."""
    monkeypatch.setattr(
        dataset_router,
        "upload_dataset",
        lambda name, lines: 42,
    )

    response = client.post(
        "/api/datasets/upload",
        data={"name": "Porto"},
        files={"file": ("data.csv", b"some csv data", "text/csv")},
    )

    assert response.status_code == 201
    assert response.json() == {
        "dataset_id": 42,
        "name": "Porto",
    }


def test_upload_dataset_name_is_stripped(monkeypatch):
    """Check whitespace is removed from the dataset name."""
    received = {}

    def fake_upload(name, lines):
        received["name"] = name
        return 42

    monkeypatch.setattr(
        dataset_router,
        "upload_dataset",
        fake_upload,
    )

    response = client.post(
        "/api/datasets/upload",
        data={"name": "  Porto  "},
        files={"file": ("data.csv", b"some csv data", "text/csv")},
    )

    assert response.status_code == 201
    assert received["name"] == "Porto"
    assert response.json()["name"] == "Porto"


def test_upload_dataset_too_large(monkeypatch):
    """Check files larger than the limit return 413."""
    monkeypatch.setattr(
        dataset_router,
        "MAX_UPLOAD_BYTES",
        1,
    )

    response = client.post(
        "/api/datasets/upload",
        data={"name": "Porto"},
        files={"file": ("data.csv", b"12", "text/csv")},
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "file is larger than 0 MB"


def test_upload_dataset_invalid_csv(monkeypatch):
    """Check invalid CSV data returns 422."""

    def fake_upload(name, lines):
        raise InvalidTrajectoryCsvError(
            [
                UploadError(
                    2,
                    "invalid trajectory",
                )
            ]
        )

    monkeypatch.setattr(
        dataset_router,
        "upload_dataset",
        fake_upload,
    )

    response = client.post(
        "/api/datasets/upload",
        data={"name": "Porto"},
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

    def fake_upload(name, lines):
        raise DatasetNameTakenError()

    monkeypatch.setattr(
        dataset_router,
        "upload_dataset",
        fake_upload,
    )

    response = client.post(
        "/api/datasets/upload",
        data={"name": "Porto"},
        files={"file": ("data.csv", b"data", "text/csv")},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "a dataset or city named 'Porto' already exists"


def test_upload_dataset_invalid_encoding(monkeypatch):
    """Check invalid UTF-8 input returns 422."""

    def fake_upload(name, lines):
        raise UnicodeDecodeError(
            "utf-8",
            b"\xff",
            0,
            1,
            "invalid start byte",
        )

    monkeypatch.setattr(
        dataset_router,
        "upload_dataset",
        fake_upload,
    )

    response = client.post(
        "/api/datasets/upload",
        data={"name": "Porto"},
        files={"file": ("data.csv", b"data", "text/csv")},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "file must be UTF-8 encoded"
