from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from services import trajectory_import_service as service


def setup_service():
    """Build the importer with mock dependencies."""
    trajectory_repository = MagicMock()
    dataset_repository = MagicMock()
    import_repository = MagicMock()
    db_actions = MagicMock()

    dataset_repository.get_dataset_id.return_value = 1

    importer = service.TrajectoryImportService(
        trajectory_repository=trajectory_repository,
        dataset_repository=dataset_repository,
        import_repository=import_repository,
        db_actions=db_actions,
    )

    return importer, import_repository, db_actions


def test_save_porto_trajectories(monkeypatch):
    """Save Porto trajectories in batches with generated source IDs."""
    importer, _, actions = setup_service()
    trajectories = [SimpleNamespace(source_id=None), SimpleNamespace(source_id=None)]
    monkeypatch.setenv("PORTO_DATASET_PATH", "porto.csv")

    def parse_porto_trajectories(path):
        return trajectories

    monkeypatch.setattr(service, "parse_porto_trajectories", parse_porto_trajectories)

    importer.save_porto_trajectories("Porto", 1)

    assert all(trajectory.source_id for trajectory in trajectories)
    assert actions.commit.call_count == 2


def test_save_porto_trajectories_without_path(monkeypatch):
    """Roll back when the Porto path is not configured."""
    importer, _, actions = setup_service()
    monkeypatch.delenv("PORTO_DATASET_PATH", raising=False)

    with pytest.raises(ValueError):
        importer.save_porto_trajectories("Porto", 1)

    actions.rollback.assert_called_once()


def test_save_beijing_trajectories(monkeypatch):
    """Save Beijing trajectories in batches with generated source IDs."""
    importer, _, actions = setup_service()
    trajectories = [SimpleNamespace(source_id=None), SimpleNamespace(source_id=None)]
    monkeypatch.setenv("BEIJING_DATASET_PATH", "beijing")

    def parse_beijing_trajectories(path):
        return trajectories

    monkeypatch.setattr(service, "parse_beijing_trajectories", parse_beijing_trajectories)

    importer.save_dataset_trajectories("Beijing", 1)

    assert all(trajectory.source_id for trajectory in trajectories)
    assert actions.commit.call_count == 2


def test_save_beijing_trajectories_without_path(monkeypatch):
    """Roll back when the Beijing path is not configured."""
    importer, _, actions = setup_service()
    monkeypatch.delenv("BEIJING_DATASET_PATH", raising=False)

    with pytest.raises(ValueError):
        importer.save_dataset_trajectories("Beijing", 1)

    actions.rollback.assert_called_once()


def test_create_uniformed_data_structure(monkeypatch):
    """Convert all source batches and return the number created."""
    importer, import_repository, actions = setup_service()
    porto = {"source_id": "porto"}
    beijing = {"source_id": "beijing"}

    import_repository.retrieve_porto_dataset_batch.side_effect = [[porto], []]
    import_repository.retrieve_beijing_data_batch.side_effect = [[beijing], []]

    def convert_trajectory(data):
        return data

    monkeypatch.setattr(service, "convert_porto_trajectory", convert_trajectory)
    monkeypatch.setattr(service, "convert_beijing_trajectory", convert_trajectory)

    assert importer.create_uniformed_data_structure(1) == 2
    assert actions.commit.call_count == 2


def test_create_uniformed_data_structure_error():
    """Roll back when source retrieval fails."""
    importer, import_repository, actions = setup_service()
    import_repository.retrieve_porto_dataset_batch.side_effect = RuntimeError("failed")

    with pytest.raises(RuntimeError):
        importer.create_uniformed_data_structure(1)

    actions.rollback.assert_called_once()
