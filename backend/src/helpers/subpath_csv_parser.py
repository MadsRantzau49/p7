from collections.abc import Iterable

from helpers.trajectory_csv_parser import parse_trajectory_csv
from models.subpath import Subpath


def parse_subpath_csv(lines: Iterable[str]) -> list[Subpath]:
    """Treat each CSV route as a complete subpath for similarity processing."""
    trajectories = parse_trajectory_csv(lines)
    next_trajectory_id = 1
    for trajectory in trajectories:
        if trajectory.trajectory_id is not None:
            next_trajectory_id = max(next_trajectory_id, trajectory.trajectory_id + 1)

    subpaths = []
    for index, trajectory in enumerate(trajectories, start=1):
        trajectory_id = trajectory.trajectory_id
        if trajectory_id is None:
            trajectory_id = next_trajectory_id
            next_trajectory_id += 1

        subpaths.append(
            Subpath(
                subpath_id=index,
                trajectory_id=trajectory_id,
                exit_a_time=trajectory.points[0].point_timestamp,
                entry_b_time=trajectory.points[-1].point_timestamp,
                points=trajectory.points,
            )
        )

    return subpaths
