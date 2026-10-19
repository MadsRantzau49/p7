from pathlib import Path

from helpers.subpath_csv_parser import parse_subpath_csv
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
    with Path(path).open(encoding="utf-8-sig", newline="") as fixture_file:
        return parse_subpath_csv(fixture_file)
