from datetime import UTC, datetime

import pytest
from helpers.similarity_steps.gps_projection_convertion import (
    centre_longitude,
    inverse_projection,
    projection,
)
from models.similarity import ProjectedPathlet, SupportInterval
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


def test_projection_requires_at_least_one_trajectory():
    """An empty list has no centre to project around."""
    with pytest.raises(ValueError, match="at least one trajectory"):
        projection([])


def test_projection_requires_every_trajectory_to_have_points():
    """A trajectory without points is rejected."""
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
    """Every trajectory keeps its identity, in the same order as the input."""
    trajectories = [
        _subtrajectory(4, 194, [(10.2, 56.15), (10.201, 56.15)]),
        _subtrajectory(
            9,
            2432,
            [(10.2, 56.16), (10.201, 56.16), (10.202, 56.16)],
        ),
    ]

    # Check whether the IDs are already wrong before projection.
    assert [t.trajectory_id for t in trajectories] == [4, 9]

    projected, _ = projection(trajectories)

    assert [t.trajectory_id for t in projected] == [4, 9]
    assert [len(t.projected_points) for t in projected] == [2, 3]


def test_inverse_projection_returns_the_original_gps_coordinates():
    """Projecting and converting back ends where it started."""
    coordinates = [(10.2, 56.15), (10.201, 56.151)]
    [projected], transformer = projection([_subtrajectory(1, 232, coordinates)])
    pathlet = ProjectedPathlet(points=projected.projected_points, count=1)

    [gps_pathlet] = inverse_projection([pathlet], transformer)

    for point, (longitude, latitude) in zip(gps_pathlet.points, coordinates, strict=True):
        assert point.longitude == pytest.approx(longitude, abs=1e-9)
        assert point.latitude == pytest.approx(latitude, abs=1e-9)


def test_inverse_projection_keeps_count_and_support_in_metres():
    """Only the points are converted, so count and support are unchanged."""
    [projected], transformer = projection([_subtrajectory(1, 232, [(10.2, 56.15), (10.201, 56.151)])])
    support = [SupportInterval(0.0, 50.0, 3)]
    pathlet = ProjectedPathlet(points=projected.projected_points, count=3, support=support)

    [gps_pathlet] = inverse_projection([pathlet], transformer)

    assert gps_pathlet.count == 3
    assert gps_pathlet.support == [SupportInterval(0.0, 50.0, 3)]
    assert pathlet.support == [SupportInterval(0.0, 50.0, 3)]


def test_inverse_projection_of_nothing_is_empty():
    """No pathlets means nothing to convert."""
    _, transformer = projection([_subtrajectory(1, 2323, [(10.2, 56.15)])])

    assert inverse_projection([], transformer) == []
