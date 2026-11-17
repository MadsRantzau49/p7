import argparse
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from dependencies import (
    get_cleaning_service,
    get_database_actions,
    get_dataset_repository,
    get_db_connection,
    get_trajectory_repository,
)
from dotenv import load_dotenv
from helpers.parsers import parse_beijing_trajectories, parse_porto_trajectories
from helpers.trajectory_helpers import convert_beijing_trajectory, convert_porto_trajectory
from models.uniformed_trajectories import UniformedTrajectories

load_dotenv()

DATASETS = {
    "porto": ("Porto", "Porto", "Europe/Lisbon", "PORTO_DATASET_PATH"),
    "beijing": ("Beijing", "Beijing", "Asia/Shanghai", "BEIJING_DATASET_PATH"),
}
BATCH_SIZE = 1000


def read_porto_trajectories(path: str) -> Iterator[UniformedTrajectories]:
    """Read the Porto file one trajectory at a time, already converted to the uniform format."""
    for raw_trajectory in parse_porto_trajectories(path):
        yield convert_porto_trajectory(raw_trajectory)


def read_beijing_trajectories(path: str) -> Iterator[UniformedTrajectories]:
    """Read the Beijing files one trajectory at a time, already converted to the uniform format."""
    for raw_trajectory in parse_beijing_trajectories(path):
        yield convert_beijing_trajectory(raw_trajectory)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import a raw dataset: convert, clean and store it")
    parser.add_argument("dataset", choices=["porto", "beijing"])
    dataset = parser.parse_args().dataset

    dataset_name, city_name, time_zone, path_variable = DATASETS[dataset]

    path = os.getenv(path_variable)
    if path is None:
        raise SystemExit(f"{path_variable} is not set")

    if dataset == "porto":
        trajectories = read_porto_trajectories(path)
    else:
        trajectories = read_beijing_trajectories(path)

    with contextmanager(get_db_connection)() as connection:
        dataset_repository = get_dataset_repository(connection)
        city = dataset_repository.get_or_create_city(city_name, time_zone)
        dataset_id = dataset_repository.create_dataset(dataset_name, city.city_id)
        connection.commit()

        service = get_cleaning_service(
            get_trajectory_repository(connection), get_database_actions(connection)
        )

        try:
            report = service.clean_dataset(dataset_id, city_name, trajectories, BATCH_SIZE)
        except BaseException:
            print(f"Import failed, deleting dataset {dataset_name}")
            connection.rollback()
            dataset_repository.delete_dataset(dataset_id)
            connection.commit()
            raise

        print(report)
