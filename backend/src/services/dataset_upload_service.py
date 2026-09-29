import uuid
from collections.abc import Iterable

from database.connection import create_db_connection
from database.queries import (
    create_dataset,
    create_source_trajectories,
    dataset_name_taken,
    insert_data_uniformed_trajectories,
)
from helpers.trajectory_csv_parser import parse_trajectory_csv
from mysql.connector import errorcode
from mysql.connector.errors import IntegrityError

BATCH_SIZE = 200


class DatasetNameTakenError(Exception):
    """A dataset, or a city, already uses that name"""


def upload_dataset(dataset_name: str, lines: Iterable[str]) -> int:
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

    context = create_db_connection()

    try:
        if dataset_name_taken(context, dataset_name):
            raise DatasetNameTakenError(dataset_name)

        dataset_id = create_dataset(context, dataset_name)

        for start in range(0, len(trajectories), BATCH_SIZE):
            batch = trajectories[start : start + BATCH_SIZE]

            source_ids = []
            for trajectory in batch:
                source_ids.append(trajectory.source_id)

            create_source_trajectories(context, dataset_id, source_ids)
            insert_data_uniformed_trajectories(context, batch)

        context.commit()
        return dataset_id

    except IntegrityError as error:
        context.rollback()
        if error.errno == errorcode.ER_DUP_ENTRY:
            raise DatasetNameTakenError(dataset_name) from error
        raise

    except Exception:
        context.rollback()
        raise

    finally:
        context.close()
