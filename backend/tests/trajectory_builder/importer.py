from pathlib import Path

from helpers.trajectory_csv_parser import parse_trajectory_csv
from models.subpath import Subpath
from models.uniformed_trajectories import UniformedTrajectories


def load_trajectories(path: str | Path) -> list[UniformedTrajectories]:
    """Load all drawn routes from a builder CSV fixture."""
    with Path(path).open(encoding="utf-8", newline="") as fixture_file:
        return parse_trajectory_csv(fixture_file)


def load_trajectory(path: str | Path) -> UniformedTrajectories:
    """Load a single trajectory fixture using the production CSV parser."""
    trajectories = load_trajectories(path)

    if len(trajectories) != 1:
        raise ValueError(f"expected one trajectory, got {len(trajectories)}")

    return trajectories[0]


def load_subpaths(path: str | Path) -> list[Subpath]:
    """Treat each drawn route as a complete subpath, without a database lookup."""
    trajectories = load_trajectories(path)
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
