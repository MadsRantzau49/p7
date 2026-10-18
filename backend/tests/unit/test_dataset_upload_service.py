from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from mysql.connector import errorcode
from mysql.connector.errors import IntegrityError
from services import dataset_upload_service as service


def setup_service(monkeypatch, trajectories=None):
    """Build the upload service with mock dependencies."""
    dataset_repository = MagicMock()
    trajectory_repository = MagicMock()
    database_actions = MagicMock()

    dataset_repository.dataset_name_taken.return_value = False
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
    trajectories = [SimpleNamespace(city=None, source_id=None) for _ in range(service.BATCH_SIZE + 1)]
    uploader, _, trajectory_repository, actions = setup_service(monkeypatch, trajectories)

    assert uploader.upload_dataset("Aalborg", ["csv"]) == 7
    assert all(item.city == "Aalborg" and item.source_id for item in trajectories)
    assert trajectory_repository.create_source_trajectories.call_count == 2
    assert trajectory_repository.insert_data_uniformed_trajectories.call_count == 2
    actions.commit.assert_called_once()
    actions.rollback.assert_not_called()


def test_upload_dataset_taken(monkeypatch):
    """Reject an existing dataset name and roll back."""
    uploader, dataset_repository, trajectory_repository, actions = setup_service(monkeypatch)
    dataset_repository.dataset_name_taken.return_value = True

    with pytest.raises(service.DatasetNameTakenError):
        uploader.upload_dataset("Porto", [])

    dataset_repository.create_dataset.assert_not_called()
    trajectory_repository.create_source_trajectories.assert_not_called()
    actions.rollback.assert_called_once()
    actions.commit.assert_not_called()


@pytest.mark.parametrize(
    ("errno", "expected"),
    [(errorcode.ER_DUP_ENTRY, service.DatasetNameTakenError), (1, IntegrityError)],
)
def test_upload_dataset_integrity_error(monkeypatch, errno, expected):
    """Translate only duplicate-key integrity errors into name errors."""
    uploader, dataset_repository, _, actions = setup_service(monkeypatch)
    dataset_repository.create_dataset.side_effect = IntegrityError(msg="failed", errno=errno)

    with pytest.raises(expected):
        uploader.upload_dataset("Porto", [])

    actions.rollback.assert_called_once()
    actions.commit.assert_not_called()
