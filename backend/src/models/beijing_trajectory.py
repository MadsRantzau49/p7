from dataclasses import dataclass


@dataclass
class TrajectoryPoint:
    date_time: str
    longitude: str
    latitude: str


@dataclass
class BeijingTrajectory:
    taxi_id: int
    points: list[TrajectoryPoint]
    source_id: int | None = None
