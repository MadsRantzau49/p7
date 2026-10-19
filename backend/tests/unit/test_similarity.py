from datetime import datetime

import pytest

from models.similarity import Coordinate, ProjectedTrajectory
from models.subpath import Subpath
from models.uniformed_trajectories import UniformedTrajectoryPoint
from services.similarity_service import SimilarityService

def make_trajectories_in_meters(trajectories: dict) -> list[ProjectedTrajectory]:
    """Build test input shaped like the output of projection.

    Takes {trajectory_id: [(x, y), ...]} and returns a list of ProjectedTrajectory.
    """
    return [
        ProjectedTrajectory(
            trajectory_id=trajectory_id,
            projected_points=[Coordinate(x=x, y=y) for x, y in points],
        )
        for trajectory_id, points in trajectories.items()
    ]

def make_subpath(trajectory_id, coordinates):
    """Build a subpath from longitude/latitude pairs."""
    timestamp = datetime(2026, 1, 1)
    return Subpath(
        subpath_id=trajectory_id,
        trajectory_id=trajectory_id,
        exit_a_time=timestamp,
        entry_b_time=timestamp,
        points=[
            UniformedTrajectoryPoint(
                longitude=longitude,
                latitude=latitude,
                point_timestamp=timestamp,
            )
            for longitude, latitude in coordinates
        ],
    )


def test_projection():
    """Project geographic points to known UTM coordinates while preserving their order."""
    service = SimilarityService()
    subpath = make_subpath(42, [(9, 0), (9.001, 0)])

    result = service.projection([subpath])

    assert len(result) == 1
    trajectory = result[0]
    assert trajectory.trajectory_id == 42
    assert len(trajectory.projected_points) == 2

    first_point = trajectory.projected_points[0]
    second_point = trajectory.projected_points[1]
    assert first_point.x == pytest.approx(500000, rel=0, abs=0.001)
    assert first_point.y == pytest.approx(0, abs=0.001)
    assert second_point.x == pytest.approx(500111.275, rel=0, abs=0.001)
    assert second_point.y == pytest.approx(0, abs=0.001)


def test_projection_northern_hemisphere():
    """Project a point north of the equator."""
    service = SimilarityService()
    subpath = make_subpath(1, [(9, 45)])

    result = service.projection([subpath])

    point = result[0].projected_points[0]
    assert point.x == pytest.approx(500000, rel=0, abs=0.001)
    assert point.y == pytest.approx(4982950.400, rel=0, abs=0.001)


def test_projection_southern_hemisphere():
    """Project a point south of the equator."""
    service = SimilarityService()
    subpath = make_subpath(1, [(9, -45)])

    result = service.projection([subpath])

    point = result[0].projected_points[0]
    assert point.x == pytest.approx(500000, rel=0, abs=0.001)
    assert point.y == pytest.approx(5017049.600, rel=0, abs=0.001)


def test_projection_uses_shared_zone():
    """Keep trajectories in the same UTM zone even across a zone boundary."""
    service = SimilarityService()
    subpaths = [make_subpath(42, [(3, 0)]), make_subpath(7, [(9, 0)])]

    result = service.projection(subpaths)

    assert len(result) == 2
    assert result[0].trajectory_id == 42
    assert result[1].trajectory_id == 7
    # Their centre is 6 degrees east, so both points use UTM zone 32N.
    assert result[0].projected_points[0].x == pytest.approx(-168881.689, rel=0, abs=0.001)
    assert result[1].projected_points[0].x == pytest.approx(500000, rel=0, abs=0.001)
    assert result[0].projected_points[0].y == pytest.approx(0, abs=0.001)
    assert result[1].projected_points[0].y == pytest.approx(0, abs=0.001)


def test_projection_empty_input():
    """Reject an empty list of subpaths."""
    service = SimilarityService()

    with pytest.raises(ValueError, match="Projection requires at least one trajectory"):
        service.projection([])


def test_projection_without_points():
    """Reject a subpath with no geographic points."""
    service = SimilarityService()
    subpath = make_subpath(42, [])

    with pytest.raises(ValueError, match="Each trajectory must contain at least one point"):
        service.projection([subpath])


def test_projection_with_empty_and_nonempty_trajectories():
    """Reject an empty trajectory even when another trajectory has points."""
    service = SimilarityService()
    subpaths = [make_subpath(1, [(9, 45)]), make_subpath(2, [])]

    with pytest.raises(ValueError, match="Each trajectory must contain at least one point"):
        service.projection(subpaths)


def test_four_points_give_three_segments():
    """Create a segment for each consecutive pair of points."""
    # (a, b, c, d) -> (a, b), (b, c), (c, d)
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
 
