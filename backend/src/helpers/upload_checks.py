from haversine import haversine, Unit

from helpers.upload_parser import MAX_ERRORS, UploadError
from models.upload_row import UploadRow

MAX_SPEED_KMH = 300

def distance_km(a: UploadRow, b: UploadRow) -> float:
    """Great-circle distance between two points, using the haversine library"""
    return haversine((a.latitude, a.longitude), (b.latitude, b.longitude), unit=Unit.KILOMETERS)

def sort_and_check_trajectories(trajectories: dict[str, list[tuple[int, UploadRow]]]) -> list[UploadError]:
    """Check that trajectories are in line with the rules set, e.g. MAX_SPEED_KMH

    Each trajectory is checked by calling sort_and_check_one_trajectory.

    Args:
        trajectories: The trajectories returned by parse_upload from upload_parser.py

    Returns:
        Every problem found, with the line it was on. An empty list means all trajectories are valid.

    Note:
        Sorts each trajectory's points by timestamp.
    """
    errors: list[UploadError] = []

    for trajectory_id, rows in trajectories.items():
        errors += sort_and_check_one_trajectory(rows)

        if len(errors) >= MAX_ERRORS:
            break

    return errors

def sort_and_check_one_trajectory(rows: list[tuple[int, UploadRow]]) -> list[UploadError]:
    """Sort one trajectory's point by time and check that they form a valid trajectory.

    Rules:
        - at least 2 points
        - the same vehicle_id and vehicle_type on every point
        - no points have the same exact timestamp
        - no movement faster than MAX_SPEED_KMH between two points in a row

    Args:
        rows: The trajectory's points, as (line number, row) pairs.

    Returns:
        Every problem found.
    """
    errors: list[UploadError] = []

    rows.sort(key=get_timestamp)

    first_line, first_row = rows[0]
    trajectory_id = first_row.trajectory_id

    if len(rows) < 2:
        errors.append(UploadError(first_line, f"trajectory {trajectory_id} has only 1 point, needs at least 2"))
        return errors

    for i in range(1, len(rows)):
        previous_line, previous_row = rows[i - 1]
        line, row = rows[i]

        if row.vehicle_id != first_row.vehicle_id or row.vehicle_type != first_row.vehicle_type:
            errors.append(UploadError(line, f"trajectory {trajectory_id} has vehicle {row.vehicle_id} "
                                            f"{row.vehicle_type}, but line {first_line} has {first_row.vehicle_id} "
                                            f"{first_row.vehicle_type}"))

        seconds = (row.timestamp - previous_row.timestamp).total_seconds()

        if seconds == 0:
            errors.append(UploadError(line, f"same timestamp as line {previous_line} in trajectory {trajectory_id}"))
            continue

        hours = seconds / 3600
        speed = distance_km(previous_row, row) / hours

        if speed > MAX_SPEED_KMH:
            errors.append(UploadError(line, f"moving {speed:.0f} km/h since line {previous_line}, "
                                            f"max is {MAX_SPEED_KMH}"))

    return errors

def get_timestamp(pair: tuple[int, UploadRow]):
    line, row = pair
    return row.timestamp