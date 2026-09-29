from pathlib import Path

from helpers.trajectory_csv_parser import parse_trajectory_csv
from models.uniformed_trajectories import UniformedTrajectories


def load_trajectory(path: str | Path) -> UniformedTrajectories:
    """Load a single trajectory fixture using the production CSV parser."""
    with Path(path).open(encoding="utf-8", newline="") as fixture_file:
        trajectories = parse_trajectory_csv(fixture_file)

    if len(trajectories) != 1:
        raise ValueError(f"expected one trajectory, got {len(trajectories)}")

    return trajectories[0]
