import argparse
import sys
from contextlib import contextmanager
from pathlib import Path

from models.city import City

sys.path.append(str(Path(__file__).parent.parent))

from dependencies import (
    get_database_actions,
    get_dataset_repository,
    get_db_connection,
    get_import_repository,
    get_trajectory_repository,
)
from services.trajectory_import_service import TrajectoryImportService

DATASETS = {
    "porto": ("Porto", "Porto", "Europe/Lisbon"),
    "beijing": ("Beijing", "Beijing", "Asia/Shanghai"),
}
BATCH_SIZE = 1000

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import a raw dataset or build the uniformed trajectories")
    parser.add_argument("stage", choices=["porto", "beijing", "uniformed"])
    stage = parser.parse_args().stage

    with contextmanager(get_db_connection)() as connection:
        dataset_repository = get_dataset_repository(connection)
        service = TrajectoryImportService(
            trajectory_repository=get_trajectory_repository(connection),
            dataset_repository=dataset_repository,
            import_repository=get_import_repository(connection),
            db_actions=get_database_actions(connection),
        )

        if stage == "uniformed":
            service.create_uniformed_data_structure(BATCH_SIZE)
        else:
            dataset_name, city_name, time_zone = DATASETS[stage]

            city = dataset_repository.get_or_create_city(city_name, time_zone)
            dataset_repository.create_dataset(dataset_name, city.city_id)
            connection.commit()

            if stage == "porto":
                service.save_porto_trajectories(dataset_name, BATCH_SIZE)
            else:
                service.save_dataset_trajectories(dataset_name, BATCH_SIZE)
