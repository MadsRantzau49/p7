from collections.abc import Iterable

from mysql.connector import errorcode
from mysql.connector.errors import IntegrityError

from database.connection import create_db_connection
from database.queries import (
    create_dataset,
    create_source_trajectories,
    dataset_name_taken,
    insert_data_uniformed_trajectories
)
from helpers.trajectory_helpers import convert_upload_trajectory
# from helpers.upload_checks import sort_and_check_trajectories
from helpers.upload_parser import MAX_ERRORS, UploadError, parse_upload

BATCH_SIZE = 200

class UploadRejected(Exception):
    """The file broke the format rules. Nothing was stored"""

    def __init__(self, errors: list[UploadError]):
        super().__init__(f"{len(errors)} problems in the uploaded file")
        self.errors = errors

class DatasetNameTaken(Exception):
    """A dataset, or a city, already uses that name"""

def upload_dataset(dataset_name: str, lines: Iterable[str]) -> int:
    """Validate an uploaded CSV and store it as a new dataset.

    Args:
        dataset_name: The new dataset's name, also used as the city.
        lines: The uploaded file's text.

    Returns:
        The new dataset_id

    Raises:
        UploadRejected: The file broke a rule. Nothing was written.
        DatasetNameTaken: The name is already in use. Nothing was written.
    """
    trajectories, errors = parse_upload(lines)
    # errors += sort_and_check_trajectories(trajectories)

    if not errors and not trajectories:
        errors.append(UploadError(1, "the file has a header but no data rows"))

    if errors:
        raise UploadRejected(errors[:MAX_ERRORS])

    context = create_db_connection()

    try:
        if dataset_name_taken(context, dataset_name):
            raise DatasetNameTaken(dataset_name)

        dataset_id = create_dataset(context, dataset_name)

        uniformed = []
        for rows in trajectories.values():
            uniformed.append(convert_upload_trajectory(rows, dataset_name))

        for start in range(0, len(uniformed), BATCH_SIZE):
            batch = uniformed[start:start + BATCH_SIZE]

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
            raise DatasetNameTaken(dataset_name) from error
        raise

    except Exception:
        context.rollback()
        raise

    finally:
        context.close()