from dataclasses import dataclass

from models.uniformed_trajectories import UniformedTrajectoryPoint

@dataclass
class Coordinate:
    x: float
    y: float

@dataclass
class TrajectoryInMeters:
    trajectory_id: int
    meter_points: list[Coordinate]

@dataclass
class Pathlet:
    pathlet_id: int
    count: int
    trajectories_included: list[int]
    start_point: UniformedTrajectoryPoint
    end_point: UniformedTrajectoryPoint