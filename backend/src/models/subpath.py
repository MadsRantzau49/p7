from dataclasses import dataclass
from datetime import datetime

from models.uniformed_trajectories import UniformedTrajectoryPoint


@dataclass
class Subpath:
    subpath_id: int
    trajectory_id: int
    exit_a_time: datetime
    entry_b_time: datetime
    points: list[UniformedTrajectoryPoint]
