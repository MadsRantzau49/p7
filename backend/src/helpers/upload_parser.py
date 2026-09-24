import csv
from collections.abc import Iterable
from dataclasses import dataclass

from models.upload_row import UploadRow
from pydantic import ValidationError

EXPECTED_HEADER = [
    "trajectory_id",
    "vehicle_id",
    "vehicle_type",
    "timestamp",
    "longitude",
    "latitude",
]
MAX_ERRORS = 100


@dataclass
class UploadError:
    line: int
    message: str


def parse_upload(
    lines: Iterable[str],
) -> tuple[dict[str, list[tuple[int, UploadRow]]], list[UploadError]]:
    """Read an uploaded CSV and group its valid rows into trajectories.

    The first row must match EXPECTED_HEADER.
    All other rows are validated with UploadRow, blank lines are skipped.

    Args:
        lines: The file's text.

    Returns:
        A tuple (trajectories, errors).
        trajectories maps each trajectory_id to its valid rows as (line number, row) pairs.
        errors lists every problem found. Line numbers count from 1, line 1 is the header.

        Valid rows are returned even when there are errors in the file.
        The caller must reject the upload if errors is not empty.
    """
    reader = csv.reader(lines)
    trajectories: dict[str, list[tuple[int, UploadRow]]] = {}
    errors: list[UploadError] = []

    header = next(reader, None)
    if header != EXPECTED_HEADER:
        errors.append(UploadError(1, f"header must be exactly: {','.join(EXPECTED_HEADER)}"))
        return trajectories, errors

    for values in reader:
        if len(errors) >= MAX_ERRORS:
            errors.append(UploadError(reader.line_num, f"stopped after {MAX_ERRORS} errors"))
            break

        if not values:
            continue

        line = reader.line_num

        if len(values) != len(EXPECTED_HEADER):
            errors.append(UploadError(line, f"expected {len(EXPECTED_HEADER)} values, got {len(values)}"))
            continue

        try:
            row = UploadRow(**dict(zip(EXPECTED_HEADER, values, strict=True)))
        except ValidationError as error:
            for detail in error.errors():
                field = detail["loc"][0]
                message = detail["msg"].removeprefix("Value error, ")
                errors.append(UploadError(line, f"{field}: {message}"))
            continue

        if row.trajectory_id not in trajectories:
            trajectories[row.trajectory_id] = []
        trajectories[row.trajectory_id].append((line, row))

    return trajectories, errors
