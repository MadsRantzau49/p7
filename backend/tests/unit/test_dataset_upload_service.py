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
    monkeypatch.setattr(service, "create_db_connection", lambda: context)
    monkeypatch.setattr(service, "parse_trajectory_csv", lambda lines: trajectories or [])
    monkeypatch.setattr(service, "dataset_name_taken", lambda context, name: False)
    monkeypatch.setattr(service, "create_dataset", lambda context, name: 7)
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
    monkeypatch.setattr(service, "dataset_name_taken", lambda context, name: True)

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

    def fail(context, name):
        raise IntegrityError(msg="failed", errno=errno)

    monkeypatch.setattr(service, "create_dataset", fail)

    with pytest.raises(expected):
        service.upload_dataset("Porto", [])

    context.rollback.assert_called_once()
    context.close.assert_called_once()
