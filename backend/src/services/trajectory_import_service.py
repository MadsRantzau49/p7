import os
import sys
import uuid
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from itertools import batched

from database.database_actions import DatabaseActions
from database.repositories.dataset_repository import DatasetRepository
from database.repositories.import_repository import ImportRepository
from database.repositories.trajectory_repository import TrajectoryRepository
from dotenv import load_dotenv
from helpers.parsers import parse_beijing_trajectories, parse_porto_trajectories
from helpers.trajectory_helpers import (
    convert_beijing_trajectory,
    convert_porto_trajectory,
)

load_dotenv()


class TrajectoryImportService:
    def __init__(
        self,
        trajectory_repository: TrajectoryRepository,
        dataset_repository: DatasetRepository,
        import_repository: ImportRepository,
        db_actions: DatabaseActions,
    ) -> None:
        self.trajectory_repository = trajectory_repository
        self.dataset_repository = dataset_repository
        self.import_repository = import_repository
        self.db_actions = db_actions

    def save_porto_trajectories(self, dataset_name: str, batch_size: int) -> None:
        """Save Porto trajectories to the database in batches."""

        try:
            dataset_id = self.dataset_repository.get_dataset_id(dataset_name)

            porto_path = os.getenv("PORTO_DATASET_PATH")

            if porto_path is None:
                raise ValueError("Path for Porto dataset is None!")

            for batch_tuple in batched(parse_porto_trajectories(porto_path), batch_size):
                print("Batch started")
                batch = list(batch_tuple)

                # Generate source IDs ourselves
                for trajectory in batch:
                    trajectory.source_id = str(uuid.uuid4())

                source_ids = []

                for trajectory in batch:
                    source_ids.append(trajectory.source_id)

                # Creates bridge entry
                self.trajectory_repository.create_source_trajectories(dataset_id, source_ids)

                # Inserts trajectory data, with source_id from source_trajectories table as PR and FK
                self.import_repository.insert_porto_trajectories(batch)

                self.db_actions.commit()
                print("Batch ended")

        except Exception as error:
            self.db_actions.rollback()
            print(f"Failed to save trajectories: {error}")
            raise

    def save_dataset_trajectories(self, dataset_name: str, batch_size) -> None:
        """Save trajectory data to the database in batches."""
        source_ids = []
        try:
            dataset_id = self.dataset_repository.get_dataset_id(dataset_name)

            beijing_path = os.getenv("BEIJING_DATASET_PATH")

            if beijing_path is None:
                raise ValueError("Path for Beijing dataset is None!")

            for batch_tuple in batched(parse_beijing_trajectories(beijing_path), batch_size):
                print("Batch started")
                batch = list(batch_tuple)

                for trajectory in batch:
                    trajectory.source_id = str(uuid.uuid4())

                source_ids = []

                for trajectory in batch:
                    source_ids.append(trajectory.source_id)

                self.trajectory_repository.create_source_trajectories(dataset_id, source_ids)

                self.import_repository.insert_beijing_dataset(batch)

                self.db_actions.commit()
                print("Batch ended")

        except Exception as error:
            self.db_actions.rollback()
            print(f"Failed to save beijing trajectories: {error}")
            raise

    def create_uniformed_data_structure(self, batch_size: int):
        """Convert Porto and Beijing data into the uniform trajectory format."""

        porto_total = 0
        beijing_total = 0

        try:
            # Porto
            last_source_id = None

            while True:
                porto_data = self.import_repository.retrieve_porto_dataset_batch(batch_size, last_source_id)

                if not porto_data:
                    break

                uniformed_trajectories = []

                for data in porto_data:
                    uniformed_trajectories.append(convert_porto_trajectory(data))

                self.trajectory_repository.insert_data_uniformed_trajectories(uniformed_trajectories)

                self.db_actions.commit()

                porto_total += len(uniformed_trajectories)
                last_source_id = porto_data[-1]["source_id"]

                print(f"Created {porto_total} trajectories from Porto")

            last_source_id = None

            # Beijing
            while True:
                beijing_data = self.import_repository.retrieve_beijing_data_batch(batch_size, last_source_id)

                if not beijing_data:
                    break

                uniformed_trajectories = []

                for data in beijing_data:
                    uniformed_trajectories.append(convert_beijing_trajectory(data))

                self.trajectory_repository.insert_data_uniformed_trajectories(uniformed_trajectories)

                self.db_actions.commit()

                beijing_total += len(uniformed_trajectories)
                last_source_id = beijing_data[-1]["source_id"]

                print(f"Created {beijing_total} trajectories from Beijing")

            total_created = porto_total + beijing_total

            print(f"Created {total_created} trajectories in total")

            return total_created

        except Exception as error:
            self.db_actions.rollback()
            print(f"Failed to create uniformed data structure: {error}")
            raise
