from datetime import datetime
from dataclasses import dataclass

from models.upload_row import VehicleType

@dataclass
class UniformedTrajectoryPoint:
    longitude: float
    point_timestamp: datetime
    latitude: float

@dataclass
class UniformedTrajectories:  
    vehicle_id: int
    vehicle_type: VehicleType
    trajectory_date: datetime
    points: list[UniformedTrajectoryPoint]

    trajectory_id: int | None = None
    city: str | None = None
    source_id: str | None = None
    

