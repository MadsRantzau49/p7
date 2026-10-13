from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock

import pytest
from mysql.connector import errorcode
from mysql.connector.errors import IntegrityError
from services import dataset_upload_service as service


def setup_service(monkeypatch, trajectories=None):
    """Replace dataset upload dependencies with small test doubles."""
    context = MagicMock()

    def create_db_connection():
        return context

    def parse_trajectory_csv(lines):
        return trajectories if trajectories is not None else []

    def dataset_name_taken(context, name):
        return False

    def create_dataset(context, name):
        return 7

    monkeypatch.setattr(service, "create_db_connection", create_db_connection)
    monkeypatch.setattr(service, "parse_trajectory_csv", parse_trajectory_csv)
    monkeypatch.setattr(service, "dataset_name_taken", dataset_name_taken)
    monkeypatch.setattr(service, "create_dataset", create_dataset)
    monkeypatch.setattr(service, "create_source_trajectories", MagicMock())
    monkeypatch.setattr(service, "insert_data_uniformed_trajectories", MagicMock())
    return context


def test_upload_dataset(monkeypatch):
    """Store parsed trajectories in batches and fill missing metadata."""
    trajectories = [SimpleNamespace(city=None, source_id=None) for _ in range(service.BATCH_SIZE + 1)]
    context = setup_service(monkeypatch, trajectories)

    assert service.upload_dataset("Aalborg", ["csv"]) == 7
    assert all(item.city == "Aalborg" and item.source_id for item in trajectories)
    assert cast(MagicMock, service.create_source_trajectories).call_count == 2
    assert cast(MagicMock, service.insert_data_uniformed_trajectories).call_count == 2
    context.commit.assert_called_once()
    context.close.assert_called_once()


def test_upload_dataset_taken(monkeypatch):
    """Reject an existing dataset name and roll back."""
    context = setup_service(monkeypatch)

    def dataset_name_taken(context, name):
        return True

    monkeypatch.setattr(service, "dataset_name_taken", dataset_name_taken)

    with pytest.raises(service.DatasetNameTakenError):
        service.upload_dataset("Porto", [])

    context.rollback.assert_called_once()
    context.close.assert_called_once()


@pytest.mark.parametrize(
    ("errno", "expected"),
    [(errorcode.ER_DUP_ENTRY, service.DatasetNameTakenError), (1, IntegrityError)],
)
def test_upload_dataset_integrity_error(monkeypatch, errno, expected):
    """Translate only duplicate-key integrity errors into name errors."""
    context = setup_service(monkeypatch)

    def raise_integrity_error(context, name):
        raise IntegrityError(msg="failed", errno=errno)

    monkeypatch.setattr(service, "create_dataset", raise_integrity_error)

    with pytest.raises(expected):
        service.upload_dataset("Porto", [])

    context.rollback.assert_called_once()
    context.close.assert_called_once()
