from dataclasses import dataclass


@dataclass
class PortoTrajectory:
    trip_id: int
    call_type: str | None
    origin_call: str | None
    origin_stand: str | None
    taxi_id: int
    timestamp: int
    day_type: str | None
    missing_data: bool
    polyline: list[list[float]]
