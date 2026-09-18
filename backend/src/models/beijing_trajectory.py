from dataclasses import dataclass

@dataclass
class beijing_trajectory:
    taxi_id: int
    points: list[trajectory_point]
    source_id: int | None = None 


@dataclass
class trajectory_point:
    date_time: str
    longitude: str
    latitude: str