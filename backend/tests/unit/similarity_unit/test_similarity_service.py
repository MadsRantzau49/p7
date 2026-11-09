import math
from datetime import UTC, datetime

import pytest
from models.similarity import GPSCoordinate, Pathlet
from models.subtrajectory import Subtrajectory
from models.uniformed_trajectories import UniformedTrajectoryPoint
from services.similarity_service import SimilarityService

MOMENT = datetime(2026, 1, 1, tzinfo=UTC)
ROUTE = [(10.2, 56.15), (10.201, 56.151), (10.202, 56.152)]


def _subtrajectory(trajectory_id: int, coordinates: list[tuple[float, float]]) -> Subtrajectory:
    """Build a subtrajectory from (longitude, latitude) pairs."""
    points = [
        UniformedTrajectoryPoint(longitude=longitude, point_timestamp=MOMENT, latitude=latitude)
        for longitude, latitude in coordinates
    ]
    return Subtrajectory(trajectory_id, trajectory_id, MOMENT, MOMENT, points)


def _shifted_north(coordinates: list[tuple[float, float]], degrees: float) -> list[tuple[float, float]]:
    """Return the same route moved north by a number of degrees of latitude."""
    return [(longitude, latitude + degrees) for longitude, latitude in coordinates]


def test_absent_input_returns_none():
    """None stays None, so callers can tell it apart from an empty result."""
    assert SimilarityService().find_similar_trajectories(None, 1) is None


def test_empty_input_returns_an_empty_list():
    """An empty query result gives no pathlets."""
    assert SimilarityService().find_similar_trajectories([], 1) == []


@pytest.mark.parametrize("epsilon", [-1, math.nan, math.inf])
def test_invalid_epsilon_is_rejected(epsilon):
    """Epsilon must be a usable distance, even when there is nothing to process."""
    with pytest.raises(ValueError, match="epsilon must be finite and non-negative"):
        SimilarityService().find_similar_trajectories([], epsilon)


def test_subtrajectory_with_fewer_than_two_points_is_rejected():
    """A subtrajectory needs at least one segment."""
    subtrajectories = [_subtrajectory(1, ROUTE), _subtrajectory(2, ROUTE[:1])]

    with pytest.raises(ValueError, match="at least two points"):
        SimilarityService().find_similar_trajectories(subtrajectories, 1)


def test_identical_routes_return_one_pathlet_in_gps_coordinates():
    """The result is one pathlet along the route with its support in metres."""
    subtrajectories = [_subtrajectory(1, ROUTE), _subtrajectory(2, ROUTE)]

    result = SimilarityService().find_similar_trajectories(subtrajectories, 1)

    assert result is not None
    [pathlet] = result
    assert isinstance(pathlet, Pathlet)
    assert all(isinstance(point, GPSCoordinate) for point in pathlet.points)
    for point, (longitude, latitude) in zip(pathlet.points, ROUTE, strict=True):
        assert point.longitude == pytest.approx(longitude, abs=1e-9)
        assert point.latitude == pytest.approx(latitude, abs=1e-9)
    assert pathlet.count == 2
    [interval] = pathlet.support
    assert interval.count == 2
    assert interval.end_m > interval.start_m


def test_routes_far_apart_return_separate_pathlets():
    """Routes in different places are not merged."""
    subtrajectories = [_subtrajectory(1, ROUTE), _subtrajectory(2, _shifted_north(ROUTE, 0.1))]

    result = SimilarityService().find_similar_trajectories(subtrajectories, 1)

    assert result is not None
    assert [pathlet.count for pathlet in result] == [1, 1]


@pytest.mark.parametrize(("epsilon", "expected_counts"), [(5, [2]), (0.1, [1, 1])])
def test_epsilon_is_a_distance_in_metres(epsilon, expected_counts):
    """Routes about 1.1 m apart merge with a 5 m tolerance but not with a 0.1 m one."""
    subtrajectories = [_subtrajectory(1, ROUTE), _subtrajectory(2, _shifted_north(ROUTE, 0.00001))]

    result = SimilarityService().find_similar_trajectories(subtrajectories, epsilon)

    assert result is not None
    assert [pathlet.count for pathlet in result] == expected_counts
