from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest
from psycopg import errors
from services import dataset_upload_service as service


def setup_service(monkeypatch, trajectories=None):
    """Build the upload service with mock dependencies."""
    dataset_repository = MagicMock()
    trajectory_repository = MagicMock()
    database_actions = MagicMock()

    dataset_repository.get_time_zones.return_value = ["Europe/Copenhagen", "Europe/Lisbon"]
    dataset_repository.dataset_name_taken.return_value = False
    dataset_repository.get_or_create_city.return_value = SimpleNamespace(
        city_id=3, name="Aalborg", time_zone="Europe/Copenhagen"
    )
    dataset_repository.create_dataset.return_value = 7

    def parse_trajectory_csv(lines):
        return trajectories if trajectories is not None else []

    monkeypatch.setattr(service, "parse_trajectory_csv", parse_trajectory_csv)

    uploader = service.UploadDataset(
        database_actions=database_actions,
        trajectory_repository=trajectory_repository,
        dataset_repository=dataset_repository,
    )

    return uploader, dataset_repository, trajectory_repository, database_actions


def test_upload_dataset(monkeypatch):
    """Store parsed trajectories in batches and fill missing metadata."""
    trajectories = [
        SimpleNamespace(
            city=None,
            source_id=None,
            trajectory_date=datetime(2024, 1, 31, 14, 5),
            points=[SimpleNamespace(point_timestamp=datetime(2024, 1, 31, 14, 5))],
        )
        for _ in range(service.BATCH_SIZE + 1)
    ]
    uploader, dataset_repository, trajectory_repository, actions = setup_service(monkeypatch, trajectories)

    assert uploader.upload_dataset("Aalborg 2024", "Aalborg", "Europe/Copenhagen", ["csv"]) == 7
    assert all(item.city == "Aalborg" and item.source_id for item in trajectories)
    copenhagen_zone = ZoneInfo("Europe/Copenhagen")
    assert trajectories[0].trajectory_date == datetime(2024, 1, 31, 14, 5, tzinfo=copenhagen_zone)
    assert trajectories[0].trajectory_date == datetime(2024, 1, 31, 13, 5, tzinfo=UTC)
    assert trajectory_repository.create_source_trajectories.call_count == 2
    assert trajectory_repository.insert_data_uniformed_trajectories.call_count == 2
    actions.commit.assert_called_once()
    actions.rollback.assert_not_called()


def test_upload_dataset_taken(monkeypatch):
    """Reject an existing dataset name and roll back."""
    uploader, dataset_repository, trajectory_repository, actions = setup_service(monkeypatch)
    dataset_repository.dataset_name_taken.return_value = True

    with pytest.raises(service.DatasetNameTakenError):
        uploader.upload_dataset("Porto", "Porto", "Europe/Lisbon", [])

    dataset_repository.create_dataset.assert_not_called()
    trajectory_repository.create_source_trajectories.assert_not_called()
    actions.rollback.assert_called_once()
    actions.commit.assert_not_called()


def test_upload_dataset_city_time_zone_mismatch(monkeypatch):
    """Rejest a time zone that differs from the existing city's and roll back."""
    uploader, dataset_repository, _, actions = setup_service(monkeypatch)

    with pytest.raises(service.CityTimeZoneMismatchError) as caught:
        uploader.upload_dataset("Aalborg 2024", "Aalborg", "Europe/Lisbon", [])

    assert caught.value.city == "Aalborg"
    assert caught.value.time_zone == "Europe/Copenhagen"
    dataset_repository.create_dataset.assert_not_called()
    actions.rollback.assert_called_once()
    actions.commit.assert_not_called()


@pytest.mark.parametrize(
    ("constraint_name", "expected"),
    [
        ("datasets_name_key", service.DatasetNameTakenError),
        ("source_trajectories_pkey", errors.UniqueViolation),
    ],
)
def test_upload_dataset_integrity_error(monkeypatch, constraint_name, expected):
    """Translate only a duplicate dataset name into a name error."""
    uploader, dataset_repository, _, actions = setup_service(monkeypatch)
    diagnostic = SimpleNamespace(constraint_name=constraint_name)
    monkeypatch.setattr(errors.UniqueViolation, "diag", property(lambda error: diagnostic))
    dataset_repository.create_dataset.side_effect = errors.UniqueViolation("duplicate key")

    with pytest.raises(expected):
        uploader.upload_dataset("Aalborg 2024", "Aalborg", "Europe/Copenhagen", [])

    actions.rollback.assert_called_once()
    actions.commit.assert_not_called()


def test_get_time_zones(monkeypatch):
    """Pass the repository's time zones through."""
    uploader, _, _, _ = setup_service(monkeypatch)

    assert uploader.get_time_zones() == ["Europe/Copenhagen", "Europe/Lisbon"]
