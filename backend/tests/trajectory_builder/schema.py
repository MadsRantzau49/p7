"""On-disk contract used by both the map builder and the clustering fixtures."""

from pathlib import Path

DATA_DIRECTORY = Path(__file__).resolve().parents[1] / "data" / "trajectories"
HEADER = (
    "trajectory_id",
    "vehicle_id",
    "vehicle_type",
    "timestamp",
    "longitude",
    "latitude",
    "city",
    "source_id",
    "database_trajectory_id",
)
