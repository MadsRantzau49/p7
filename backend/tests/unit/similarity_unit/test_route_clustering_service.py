from datetime import UTC, datetime

import pytest
from models.similarity import GPSCoordinate, Route
from models.subtrajectory import Subtrajectory
from models.uniformed_trajectories import UniformedTrajectoryPoint
from services.clustering_service import ClusteringService

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
    assert ClusteringService().find_routes(None, 1) is None


def test_empty_input_returns_none():
    """An empty query result is treated like an absent one."""
    assert ClusteringService().find_routes([], 1) is None


def test_subtrajectory_with_fewer_than_two_points_is_rejected():
    """A subtrajectory needs at least one segment."""
    subtrajectories = [_subtrajectory(1, ROUTE), _subtrajectory(2, ROUTE[:1])]

    with pytest.raises(ValueError, match="at least two points"):
        ClusteringService().find_routes(subtrajectories, 1)


def test_identical_routes_return_one_route_in_gps_coordinates():
    """The result is one route along the path with its count of contributors."""
    subtrajectories = [_subtrajectory(1, ROUTE), _subtrajectory(2, ROUTE)]

    result = ClusteringService().find_routes(subtrajectories, 1)

    assert result is not None
    [route] = result
    assert isinstance(route, Route)
    assert all(isinstance(point, GPSCoordinate) for point in route.points)
    for point, (longitude, latitude) in zip(route.points, ROUTE, strict=True):
        assert point.longitude == pytest.approx(longitude, abs=1e-9)
        assert point.latitude == pytest.approx(latitude, abs=1e-9)
    assert route.count == 2


def test_routes_far_apart_return_separate_routes():
    """Routes in different places are not merged."""
    subtrajectories = [_subtrajectory(1, ROUTE), _subtrajectory(2, _shifted_north(ROUTE, 0.1))]

    result = ClusteringService().find_routes(subtrajectories, 1)

    assert result is not None
    assert [route.count for route in result] == [1, 1]


@pytest.mark.parametrize(("epsilon", "expected_counts"), [(5, [2]), (0.1, [1, 1])])
def test_epsilon_is_a_distance_in_metres(epsilon, expected_counts):
    """Routes about 1.1 m apart merge with a 5 m tolerance but not with a 0.1 m one."""
    subtrajectories = [_subtrajectory(1, ROUTE), _subtrajectory(2, _shifted_north(ROUTE, 0.00001))]

    result = ClusteringService().find_routes(subtrajectories, epsilon)

    assert result is not None
    assert [route.count for route in result] == expected_counts
