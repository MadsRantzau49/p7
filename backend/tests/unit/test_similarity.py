
import pytest
 
from models.similarity import Coordinate, TrajectoryInMeters, TrajectorySegments
from services.similariy_service import SimilarityService

def make_trajectories_in_meters(trajectories: dict) -> list[TrajectoryInMeters]:
    """Build test input shaped like the output of convert_gps_to_meter_coordinates.
 
    Takes {trajectory_id: [(x, y), ...]} and returns a list of TrajectoryInMeters.
    """
    return [
        TrajectoryInMeters(
            trajectory_id=trajectory_id,
            meter_points=[Coordinate(x=x, y=y) for x, y in points],
        )
        for trajectory_id, points in trajectories.items()
    ]
 
 
def test_four_points_give_three_segments():
    """(a, b, c, d) becomes the segments (a, b), (b, c), (c, d)."""
    trajectories = make_trajectories_in_meters({
        1: [(0, 0), (1, 0), (2, 0), (3, 0)],
    })
 
    segments = SimilarityService().generate_segments(trajectories)
 
    assert len(segments) == 3
    assert [(s.start, s.end) for s in segments] == [
        (Coordinate(x=0, y=0), Coordinate(x=1, y=0)),
        (Coordinate(x=1, y=0), Coordinate(x=2, y=0)),
        (Coordinate(x=2, y=0), Coordinate(x=3, y=0)),
    ]
 
 
def test_consecutive_segments_share_endpoint():
    """Each segment ends where the next segment in the trajectory starts."""
    trajectories = make_trajectories_in_meters({
        1: [(0, 0), (1, 1), (2, 0), (5, 3)],
    })
 
    segments = SimilarityService().generate_segments(trajectories)
 
    for current, nxt in zip(segments, segments[1:]):
        assert current.end == nxt.start
 
 
def test_segments_keep_their_trajectory_id():
    """Every segment carries the ID of the trajectory it came from."""
    trajectories = make_trajectories_in_meters({
        7: [(0, 0), (1, 0), (2, 0)],
        42: [(5, 5), (6, 6)],
    })
 
    segments = SimilarityService().generate_segments(trajectories)
 
    assert [s.trajectory_id for s in segments] == [7, 7, 42]
 
 
def test_no_trajectories_gives_no_segments():
    """An empty input list gives an empty segment list."""
    assert SimilarityService().generate_segments(make_trajectories_in_meters({})) == []
 
