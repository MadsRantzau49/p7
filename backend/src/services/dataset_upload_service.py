import uuid
from collections.abc import Iterable

from database.database_actions import DatabaseActions
from database.repositories.dataset_repository import DatasetRepository
from database.repositories.trajectory_repository import TrajectoryRepository
from helpers.trajectory_csv_parser import parse_trajectory_csv
from psycopg import errors

BATCH_SIZE = 200


class DatasetNameTakenError(Exception):
    """Another dataset already uses that name"""


class InvalidTimeZoneError(Exception):
    """The time zone is not known"""


class CityTimeZoneMismatchError(Exception):
    """The city already exists with another time zone"""

    def __init__(self, city: str, time_zone: str):
        super().__init__(city, time_zone)
        self.city = city
        self.time_zone = time_zone


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

    def upload_dataset(self, dataset_name: str, city_name: str, time_zone: str, lines: Iterable[str]) -> int:
        """Validate an uploaded CSV and store it as a new dataset.

        Args:
            dataset_name: The new dataset's name.
            city_name: The name of the city the data was recorded in.
            time_zone: The time zone of the city.
            lines: The uploaded file's text.

        Returns:
            The new dataset_id

        Raises:
            InvalidTimeZoneError: The time zone is Unknown.
            InvalidTrajectoryCsvError: The file broke a rule.
            DatasetNameTakenError: The name is already in use.
            CityTimeZoneMismatchError: The city exists with another time zone.
        """

        if time_zone not in self.dataset_repository.get_time_zones():
            raise InvalidTimeZoneError(time_zone)

        trajectories = parse_trajectory_csv(lines)

        for trajectory in trajectories:
            trajectory.city = city_name
            if trajectory.source_id is None:
                trajectory.source_id = str(uuid.uuid4())

        try:
            if self.dataset_repository.dataset_name_taken(dataset_name):
                raise DatasetNameTakenError(dataset_name)

            city = self.dataset_repository.get_or_create_city(city_name, time_zone)
            if city.time_zone != time_zone:
                raise CityTimeZoneMismatchError(city_name, city.time_zone)

            dataset_id = self.dataset_repository.create_dataset(dataset_name, city.city_id)

            for start in range(0, len(trajectories), BATCH_SIZE):
                batch = trajectories[start : start + BATCH_SIZE]

                source_ids = []
                for trajectory in batch:
                    source_ids.append(trajectory.source_id)

                self.trajectory_repository.create_source_trajectories(dataset_id, source_ids)
                self.trajectory_repository.insert_data_uniformed_trajectories(batch)

            self.database_actions.commit()
            return dataset_id

        except errors.UniqueViolation as error:
            self.database_actions.rollback()
            if error.diag.constraint_name == "datasets_name_key":
                raise DatasetNameTakenError(dataset_name) from error
            raise
        except Exception:
            self.database_actions.rollback()
            raise

    def get_time_zones(self) -> list[str]:
        """Time zones a dataset's city can use."""
        return self.dataset_repository.get_time_zones()
