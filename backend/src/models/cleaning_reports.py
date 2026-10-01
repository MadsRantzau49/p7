from dataclasses import dataclass, field
from enum import Enum 

class RejectionReason(str, Enum): 
    OUT_OF_BOUNDS = "out_of_bounds"
    BAD_TIMESTAMP = "bad_timestamp"
    IDENTICAL_RUN = "identical_run"
    SPEED_OUTLIER = "speed_outlier"
    ACCEL_OUTLIER = "accel_outlier"

@dataclass 
class JourneyReport: 
    source_id: str | None
    points_in: int = 0 
    points_out: int = 0 
    removed: dict[RejectionReason, int] = field(default_factory=dict)
    gaps_found: int = 0 
    segments_out: int = 0
    dropped: bool = False


@dataclass 
class DatasetReport: 
    city: str
    journeys_in: int = 0 
    journeys_dropped: int = 0  
    segments_out: int = 0 
    points_in: int = 0
    points_out: int = 0 
    gaps_found: int = 0
    removed: dict[RejectionReason, int] = field(default_factory=dict)