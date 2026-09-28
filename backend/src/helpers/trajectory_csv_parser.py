from collections.abc import Iterable

from helpers.trajectory_helpers import convert_upload_trajectory
from helpers.upload_checks import sort_and_check_trajectories
from helpers.upload_parser import MAX_ERRORS, UploadError, parse_upload
from models.uniformed_trajectories import UniformedTrajectories


class InvalidTrajectoryCsvError(ValueError):
    """The CSV does not satisfy the trajectory file format."""

    def __init__(self, errors: list[UploadError]):
        super().__init__(f"{len(errors)} problems in the trajectory CSV")
        self.errors = errors


def parse_trajectory_csv(lines: Iterable[str]) -> list[UniformedTrajectories]:
    """Parse and validate CSV rows as uniformed trajectories.

    Points are sorted by timestamp and optional metadata is preserved as-is.

    Raises:
        InvalidTrajectoryCsvError: The CSV does not satisfy the file format.
    """
    grouped_rows, errors = parse_upload(lines)
    errors += sort_and_check_trajectories(grouped_rows)

    if not errors and not grouped_rows:
        errors.append(UploadError(1, "the file has a header but no data rows"))

    if errors:
        raise InvalidTrajectoryCsvError(errors[:MAX_ERRORS])

    return [convert_upload_trajectory(rows) for rows in grouped_rows.values()]
