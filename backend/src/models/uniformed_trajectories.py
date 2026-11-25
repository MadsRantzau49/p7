from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class VehicleType(StrEnum):
    CAR = "CAR"
    TAXI = "TAXI"
    UNKNOWN = "UNKNOWN"


@dataclass
class UniformedTrajectoryPoint:
    longitude: float
    point_timestamp: datetime
    latitude: float


@dataclass
class UniformedTrajectories:
    vehicle_id: str
    vehicle_type: VehicleType
    trajectory_date: datetime
    points: list[UniformedTrajectoryPoint]

    trajectory_id: int | None = None
    city: str | None = None
