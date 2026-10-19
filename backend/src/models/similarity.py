from dataclasses import dataclass

from models.uniformed_trajectories import UniformedTrajectoryPoint

@dataclass
class Coordinate:
    x: float
    y: float

@dataclass
class ProjectedTrajectory:
    trajectory_id: int
    projected_points: list[Coordinate]

@dataclass
class Pathlet:
    pathlet_id: int
    count: int
    trajectories_included: list[int]
    start_point: UniformedTrajectoryPoint
    end_point: UniformedTrajectoryPoint
    
@dataclass
class TrajectorySegments:
    trajectory_id: int
    segment_index: int
    start: Coordinate
    end: Coordinate
