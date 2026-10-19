from models.uniformed_trajectories import UniformedTrajectoryPoint


class Coordinate:
    x: float
    y: float


class TrajectoryInMeters:
    trajectory_id: int
    meter_points: list[Coordinate]


class Pathlet:
    pathlet_id: int
    count: int
    trajectories_included: list[int]
    start_point: UniformedTrajectoryPoint
    end_point: UniformedTrajectoryPoint