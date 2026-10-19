
import pytest
 
from models.similarity import Coordinate, TrajectoryInMeters, TrajectorySegments
from services.similariy_service import SimilarityService

trajectory = TrajectoryInMeters(
    trajectory_id=1,
    meter_points=[Coordinate(0, 0), Coordinate(1, 0), Coordinate(2, 0), Coordinate(3, 0)],
)

def test_four_points_give_three_segments(service):
    # (a, b, c, d) -> (a, b), (b, c), (c, d)
    trajectory = make_trajectory(1, [(0, 0), (1, 0), (2, 0), (3, 0)])
 
    segments = service.generate_segments([trajectory])
 
    assert len(segments) == 3
    assert [(s.start, s.end) for s in segments] == [
        (Coordinate(0, 0), Coordinate(1, 0)),
        (Coordinate(1, 0), Coordinate(2, 0)),
        (Coordinate(2, 0), Coordinate(3, 0)),
    ]
