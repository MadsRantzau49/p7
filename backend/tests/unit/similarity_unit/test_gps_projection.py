from datetime import UTC, datetime

import pytest
from helpers.similarity_steps.gps_projection_convertion import (
    centre_longitude,
    inverse_projection,
    projection,
)
from models.similarity import ProjectedRoute
from models.subtrajectory import Subtrajectory
from models.uniformed_trajectories import UniformedTrajectoryPoint

MOMENT = datetime(2026, 1, 1, tzinfo=UTC)


def _point(longitude: float, latitude: float) -> UniformedTrajectoryPoint:
    """Build a GPS point at a fixed time."""
    return UniformedTrajectoryPoint(longitude=longitude, point_timestamp=MOMENT, latitude=latitude)


def _subtrajectory(
    trajectory_id: int, subtrajectory_id: int, coordinates: list[tuple[float, float]]
) -> Subtrajectory:
    """Build a subtrajectory from (longitude, latitude) pairs."""
    points = [_point(longitude, latitude) for longitude, latitude in coordinates]
    return Subtrajectory(trajectory_id, trajectory_id, MOMENT, MOMENT, points)


def test_centre_longitude_handles_the_antimeridian():
    """179 and -179 degrees are neighbours, so their centre is 180 degrees and not 0."""
    assert abs(centre_longitude([_point(179, 0), _point(-179, 0)])) == pytest.approx(180)


def test_projection_requires_at_least_one_subtrajectory():
    """An empty list has no centre to project around."""
    with pytest.raises(ValueError, match="at least one subtrajectory"):
        projection([])


def test_projection_requires_every_subtrajectory_to_have_points():
    """A subtrajectory without points is rejected."""
    with pytest.raises(ValueError, match="at least one point"):
        projection(
            [
                _subtrajectory(1, 104, [(10.2, 56.15)]),
                _subtrajectory(2, 204, []),
            ]
        )


def test_projection_is_centred_on_the_input():
    """A single location lies at the origin of its own projection."""
    [projected], _ = projection([_subtrajectory(1, 104, [(10.2, 56.15)])])

    assert projected.projected_points[0].x == pytest.approx(0, abs=1e-6)
    assert projected.projected_points[0].y == pytest.approx(0, abs=1e-6)


def test_projection_gives_distances_in_metres():
    """A thousandth of a degree of latitude is about 111 metres."""
    [projected], _ = projection([_subtrajectory(1, 104, [(10.2, 56.15), (10.2, 56.151)])])

    first, second = projected.projected_points
    assert second.y - first.y == pytest.approx(111.3, rel=0.01)
    assert second.x - first.x == pytest.approx(0, abs=0.01)


def test_projection_keeps_trajectory_ids_and_the_number_of_points():
    """Every subtrajectory keeps its identity, in the same order as the input."""
    subtrajectories = [
        _subtrajectory(4, 194, [(10.2, 56.15), (10.201, 56.15)]),
        _subtrajectory(9, 2432, [(10.2, 56.16), (10.201, 56.16), (10.202, 56.16)]),
    ]

    assert [s.trajectory_id for s in subtrajectories] == [4, 9]

    projected, _ = projection(subtrajectories)

    assert [p.trajectory_id for p in projected] == [4, 9]
    assert [len(p.projected_points) for p in projected] == [2, 3]


def test_inverse_projection_returns_the_original_gps_coordinates():
    """Projecting and converting back ends where it started."""
    coordinates = [(10.2, 56.15), (10.201, 56.151)]
    [projected], transformer = projection([_subtrajectory(1, 232, coordinates)])
    route = ProjectedRoute(points=projected.projected_points, count=1)

    [gps_route] = inverse_projection([route], transformer)

    for point, (longitude, latitude) in zip(gps_route.points, coordinates, strict=True):
        assert point.longitude == pytest.approx(longitude, abs=1e-9)
        assert point.latitude == pytest.approx(latitude, abs=1e-9)


def test_inverse_projection_keeps_the_count():
    """Only the points are converted, so the count is unchanged."""
    [projected], transformer = projection([_subtrajectory(1, 232, [(10.2, 56.15), (10.201, 56.151)])])
    route = ProjectedRoute(points=projected.projected_points, count=3)

    [gps_route] = inverse_projection([route], transformer)

    assert gps_route.count == 3


def test_inverse_projection_of_nothing_is_empty():
    """No routes means nothing to convert."""
    _, transformer = projection([_subtrajectory(1, 2323, [(10.2, 56.15)])])

    assert inverse_projection([], transformer) == []
