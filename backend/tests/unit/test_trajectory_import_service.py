from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from services import trajectory_import_service as service


def setup_service(monkeypatch):
    """Replace the importer database connection with a test double."""
    context = MagicMock()
    monkeypatch.setattr(service, "create_db_connection", lambda: context)
    monkeypatch.setattr(service.database.queries, "get_dataset_id", lambda context, name: 1)
    return context


def test_save_porto_trajectories(monkeypatch):
    """Save Porto trajectories in batches with generated source IDs."""
    context = setup_service(monkeypatch)
    trajectories = [SimpleNamespace(source_id=None), SimpleNamespace(source_id=None)]
    monkeypatch.setenv("PORTO_DATASET_PATH", "porto.csv")
    monkeypatch.setattr(service, "parse_porto_trajectories", lambda path: trajectories)
    monkeypatch.setattr(service.database.queries, "create_source_trajectories", MagicMock())
    monkeypatch.setattr(service.database.queries, "insert_porto_trajectories", MagicMock())

    service.save_porto_trajectories("Porto", 1)

    assert all(trajectory.source_id for trajectory in trajectories)
    assert context.commit.call_count == 2
    context.close.assert_called_once()


def test_save_porto_trajectories_without_path(monkeypatch):
    """Roll back when the Porto path is not configured."""
    context = setup_service(monkeypatch)
    monkeypatch.delenv("PORTO_DATASET_PATH", raising=False)

    with pytest.raises(ValueError):
        service.save_porto_trajectories("Porto", 1)

    context.rollback.assert_called_once()
    context.close.assert_called_once()


def test_save_beijing_trajectories(monkeypatch):
    """Save Beijing trajectories in batches with generated source IDs."""
    context = setup_service(monkeypatch)
    trajectories = [SimpleNamespace(source_id=None), SimpleNamespace(source_id=None)]
    monkeypatch.setenv("BEIJING_DATASET_PATH", "beijing")
    monkeypatch.setattr(service, "parse_beijing_trajectories", lambda path: trajectories)
    monkeypatch.setattr(service.database.queries, "create_source_trajectories", MagicMock())
    monkeypatch.setattr(service.database.queries, "insert_beijing_dataset", MagicMock())

    service.save_dataset_trajectories("Beijing", 1)

    assert all(trajectory.source_id for trajectory in trajectories)
    assert context.commit.call_count == 2
    context.close.assert_called_once()


def test_save_beijing_trajectories_without_path(monkeypatch):
    """Roll back when the Beijing path is not configured."""
    context = setup_service(monkeypatch)
    monkeypatch.delenv("BEIJING_DATASET_PATH", raising=False)

    with pytest.raises(ValueError):
        service.save_dataset_trajectories("Beijing", 1)

    context.rollback.assert_called_once()
    context.close.assert_called_once()


def test_create_uniformed_data_structure(monkeypatch):
    """Convert all source batches and return the number created."""
    context = setup_service(monkeypatch)
    porto = {"source_id": "porto"}
    beijing = {"source_id": "beijing"}
    monkeypatch.setattr(
        service.database.queries, "retrieve_porto_dataset_batch", MagicMock(side_effect=[[porto], []])
    )
    monkeypatch.setattr(
        service.database.queries, "retrieve_beijing_data_batch", MagicMock(side_effect=[[beijing], []])
    )
    monkeypatch.setattr(service, "convert_porto_trajectory", lambda data: data)
    monkeypatch.setattr(service, "convert_beijing_trajectory", lambda data: data)
    monkeypatch.setattr(service.database.queries, "insert_data_uniformed_trajectories", MagicMock())

    assert service.create_uniformed_data_structure(1) == 2
    assert context.commit.call_count == 2
    context.close.assert_called_once()


def test_create_uniformed_data_structure_error(monkeypatch):
    """Roll back when source retrieval fails."""
    context = setup_service(monkeypatch)
    monkeypatch.setattr(
        service.database.queries,
        "retrieve_porto_dataset_batch",
        MagicMock(side_effect=RuntimeError("failed")),
    )

    with pytest.raises(RuntimeError):
        service.create_uniformed_data_structure(1)

    context.rollback.assert_called_once()
    context.close.assert_called_once()
