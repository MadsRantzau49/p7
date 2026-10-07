from datetime import date

from database.connection import create_db_connection
from database.queries import get_candidate_segments, get_trajectory_points
from helpers.subpath_cutting import (
    build_subpath_points,
    group_by_trajectory,
    make_box,
    trajectory_subpaths,
)
from models.subpath import Subpath


def find_subpaths(
    a_longitude: float,
    a_latitude: float,
    b_longitude: float,
    b_latitude: float,
    start_date: date,
    end_date: date,
    box_half_width_m: float,
) -> list[Subpath]:
    """Find the sub-paths from location A to location B in the date-range given."""
    if start_date > end_date:
        raise ValueError("start_date must be on or before end_date")
    if box_half_width_m <= 0:
        raise ValueError("box_half_width_m must be greater than 0")

    box_a = make_box(a_longitude, a_latitude, box_half_width_m)
    box_b = make_box(b_longitude, b_latitude, box_half_width_m)

    if box_a.intersects(box_b):
        raise ValueError("box A and box B must not overlap")

    context = create_db_connection()

    try:
        rows = get_candidate_segments(context, box_a.bounds, box_b.bounds, start_date, end_date)
        segments_by_trajectory = group_by_trajectory(rows)

        pairs_by_trajectory = {}

        for trajectory_id in segments_by_trajectory:
            pairs = trajectory_subpaths(segments_by_trajectory[trajectory_id], box_a, box_b)

            if len(pairs) > 0:
                pairs_by_trajectory[trajectory_id] = pairs

        points_by_trajectory = get_trajectory_points(context, list(pairs_by_trajectory))
    finally:
        context.close()

    subpaths = []

    for trajectory_id in pairs_by_trajectory:
        for exit_a, enter_b in pairs_by_trajectory[trajectory_id]:
            path = build_subpath_points(points_by_trajectory[trajectory_id], exit_a, enter_b)

            subpaths.append(
                Subpath(
                    subpath_id=len(subpaths) + 1,
                    trajectory_id=trajectory_id,
                    exit_a_time=exit_a.time,
                    entry_b_time=enter_b.time,
                    points=path,
                )
            )

    return subpaths
