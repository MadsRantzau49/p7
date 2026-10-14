import uuid
from collections.abc import Iterable

from database.database_actions import DatabaseActions
from database.repositories.dataset_repository import DatasetRepository
from database.repositories.trajectory_repository import TrajectoryRepository
from helpers.trajectory_csv_parser import parse_trajectory_csv
from mysql.connector import errorcode
from mysql.connector.errors import IntegrityError

BATCH_SIZE = 200


class DatasetNameTakenError(Exception):
    """A dataset, or a city, already uses that name"""


class UploadDataset:
    def __init__(
        self,
        database_actions: DatabaseActions,
        trajectory_repository: TrajectoryRepository,
        dataset_repository: DatasetRepository,
    ):
        self.database_actions = database_actions
        self.trajectory_repository = trajectory_repository
        self.dataset_repository = dataset_repository

    def upload_dataset(self, dataset_name: str, lines: Iterable[str]) -> int:
        """Validate an uploaded CSV and store it as a new dataset.

        Args:
            dataset_name: The new dataset's name, also used as the city.
            lines: The uploaded file's text.

        Returns:
            The new dataset_id

        Raises:
            InvalidTrajectoryCsvError: The file broke a rule. Nothing was written.
            DatasetNameTakenError: The name is already in use. Nothing was written.
        """
        trajectories = parse_trajectory_csv(lines)

        for trajectory in trajectories:
            trajectory.city = dataset_name
            if trajectory.source_id is None:
                trajectory.source_id = str(uuid.uuid4())

        try:
            if self.dataset_repository.dataset_name_taken(dataset_name):
                raise DatasetNameTakenError(dataset_name)

            dataset_id = self.dataset_repository.create_dataset(dataset_name)

            for start in range(0, len(trajectories), BATCH_SIZE):
                batch = trajectories[start : start + BATCH_SIZE]

                source_ids = []
                for trajectory in batch:
                    source_ids.append(trajectory.source_id)

                self.trajectory_repository.create_source_trajectories(dataset_id, source_ids)
                self.trajectory_repository.insert_data_uniformed_trajectories(batch)

            self.database_actions.commit()
            return dataset_id

        except IntegrityError as error:
            self.database_actions.rollback()
            if error.errno == errorcode.ER_DUP_ENTRY:
                raise DatasetNameTakenError(dataset_name) from error
            raise

        except Exception:
            self.database_actions.rollback()
            raise
