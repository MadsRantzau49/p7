from datetime import datetime

import pytest
from models.similarity import Coordinate, ProjectedPathlet, ProjectedTrajectory, TrajectorySection
from models.subpath import Subpath
from models.uniformed_trajectories import UniformedTrajectoryPoint
from services.similarity_service import SimilarityService


def make_subpath(trajectory_id, coordinates):
    """Build a geographic subpath from longitude/latitude pairs."""
    timestamp = datetime(2026, 10, 19)
    return Subpath(
        subpath_id=trajectory_id,
        trajectory_id=trajectory_id,
        exit_a_time=timestamp,
        entry_b_time=timestamp,
        points=[
            UniformedTrajectoryPoint(longitude=longitude, latitude=latitude, point_timestamp=timestamp)
            for longitude, latitude in coordinates
        ],
    )


def make_projected_pathlet(trajectory):
    """Use a full projected trajectory as a selected representative."""
    section = TrajectorySection(
        trajectory_id=trajectory.trajectory_id,
        start_index=0,
        end_index=len(trajectory.projected_points) - 1,
        points=trajectory.projected_points,
    )
    return ProjectedPathlet(
        pathlet_id=1,
        representative=section,
        sections=[section],
        trajectories_included=[trajectory.trajectory_id],
        count=1,
    )


def test_inverse_projection_preserves_all_points_order_and_support():
    """Recover every vertex of a bent path and keep the selected pathlet metadata."""
    service = SimilarityService()
    original = make_subpath(42, [(12, 57), (12.01, 57.02), (12.02, 57.005), (12.03, 57.025)])
    projected = service.projection([original])[0]
    meter_points_before = [(point.x, point.y) for point in projected.projected_points]
    selected = make_projected_pathlet(projected)
    selected.pathlet_id = 9
    selected.count = 2
    selected.trajectories_included = [42, 7]

    result = service.inverse_projection([selected])

    assert len(result) == 1
    pathlet = result[0]
    assert pathlet.pathlet_id == 9
    assert pathlet.count == 2
    assert pathlet.trajectories_included == [42, 7]
    assert len(pathlet.points) == 4
    for actual, expected in zip(pathlet.points, original.points, strict=True):
        assert actual.longitude == pytest.approx(expected.longitude, rel=0, abs=0.00000001)
        assert actual.latitude == pytest.approx(expected.latitude, rel=0, abs=0.00000001)
    assert [(point.x, point.y) for point in projected.projected_points] == meter_points_before


def test_inverse_projection_uses_the_shared_zone_and_preserves_pathlet_order():
    """Recover paths on both sides of a UTM boundary using Step 1's shared projection."""
    service = SimilarityService()
    first = make_subpath(7, [(5.99, 45), (5.99, 45.01)])
    second = make_subpath(88, [(6.01, 45), (6.01, 45.01)])
    projected = service.projection([first, second])
    first_pathlet = make_projected_pathlet(projected[0])
    first_pathlet.pathlet_id = 3
    second_pathlet = make_projected_pathlet(projected[1])
    second_pathlet.pathlet_id = 6

    result = service.inverse_projection([second_pathlet, first_pathlet])

    assert [pathlet.pathlet_id for pathlet in result] == [6, 3]
    assert result[0].trajectories_included == [88]
    assert result[1].trajectories_included == [7]
    assert result[0].points[0].longitude == pytest.approx(6.01, rel=0, abs=0.00000001)
    assert result[1].points[0].longitude == pytest.approx(5.99, rel=0, abs=0.00000001)
    assert result[0].points[1].latitude == pytest.approx(45.01, rel=0, abs=0.00000001)
    assert result[1].points[1].latitude == pytest.approx(45.01, rel=0, abs=0.00000001)


def test_inverse_projection_in_the_southern_hemisphere():
    """Use the southern UTM projection's inverse when recovering coordinates."""
    service = SimilarityService()
    original = make_subpath(1, [(153, -27.47), (153.001, -27.471), (153.002, -27.469)])
    projected = service.projection([original])[0]

    result = service.inverse_projection([make_projected_pathlet(projected)])

    assert len(result[0].points) == 3
    for actual, expected in zip(result[0].points, original.points, strict=True):
        assert actual.longitude == pytest.approx(expected.longitude, rel=0, abs=0.00000001)
        assert actual.latitude == pytest.approx(expected.latitude, rel=0, abs=0.00000001)


def test_inverse_projection_only_returns_the_selected_representative_section():
    """Convert an interior section without adding the original trajectory's earlier points."""
    service = SimilarityService()
    original = make_subpath(1, [(9, 45), (9.001, 45.001), (9.002, 45.003), (9.004, 45.002)])
    projected = service.projection([original])[0]
    selected = make_projected_pathlet(projected)
    selected.representative = TrajectorySection(1, 1, 3, projected.projected_points[1:4])
    selected.sections = [selected.representative]

    result = service.inverse_projection([selected])

    assert len(result[0].points) == 3
    for actual, expected in zip(result[0].points, original.points[1:4], strict=True):
        assert actual.longitude == pytest.approx(expected.longitude, rel=0, abs=0.00000001)
        assert actual.latitude == pytest.approx(expected.latitude, rel=0, abs=0.00000001)


def test_a_new_projection_updates_the_inverse_used_by_the_service():
    """Use the most recent forward projection when the service is reused."""
    service = SimilarityService()
    service.projection([make_subpath(1, [(9, 45), (9.001, 45.001)])])
    latest = make_subpath(2, [(-123, 49), (-123.001, 49.001)])
    projected = service.projection([latest])[0]

    result = service.inverse_projection([make_projected_pathlet(projected)])

    assert result[0].points[0].longitude == pytest.approx(-123, rel=0, abs=0.00000001)
    assert result[0].points[0].latitude == pytest.approx(49, rel=0, abs=0.00000001)
    assert result[0].points[1].longitude == pytest.approx(-123.001, rel=0, abs=0.00000001)
    assert result[0].points[1].latitude == pytest.approx(49.001, rel=0, abs=0.00000001)


def test_inverse_projection_requires_the_original_projection():
    """Reject metric points when the service has no forward projection to invert."""
    service = SimilarityService()
    projected = ProjectedTrajectory(1, [Coordinate(500000, 0), Coordinate(500100, 0)])

    with pytest.raises(ValueError, match="Run projection.*before inverse_projection"):
        service.inverse_projection([make_projected_pathlet(projected)])


def test_no_selected_pathlets_produce_no_gps_pathlets():
    """An empty selection has no points to convert."""
    assert SimilarityService().inverse_projection([]) == []
