from dataclasses import dataclass
from datetime import datetime


@dataclass
class TrajectorySegments:
    trajectory_id: int
    segment_index: int
    path: str
    start_time: datetime
    end_time: datetime
