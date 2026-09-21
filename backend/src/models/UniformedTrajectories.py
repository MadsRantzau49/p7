import datetime
from dataclasses import dataclass


@dataclass
class UniformedTrajectoryPoint:
    longitude: float
    point_timestamp: datetime
    latitude: float


@dataclass 
class UniformedTrajectories:  
    taxi_id: int
    trajectory_date: datetime
    points: list[UniformedTrajectoryPoint]

    trajectory_id: int | None = None
    city: str | None = None
    source_id: str | None = None