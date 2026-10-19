import datetime
from pathlib import Path

from trajectory_builder.importer import load_subpaths, load_trajectory


def test_imports_template_and_generates_timestamps():
    """Check that the CSV template is imported as a uniformed trajectory."""
    fixture = Path(__file__).parent.parent / "data" / "trajectories" / "template.csv"

    trajectory = load_trajectory(fixture)

    assert trajectory.trajectory_id is None
    assert trajectory.vehicle_id == 0
    assert trajectory.vehicle_type == "UNKNOWN"
    assert trajectory.city == "Test"
    assert trajectory.trajectory_date == datetime.datetime(2026, 9, 21, 8, 0)
    assert [(point.latitude, point.longitude) for point in trajectory.points] == [
        (57.0252, 9.8981),
        (57.0294, 9.9018),
        (57.0337, 9.9062),
        (57.0381, 9.9116),
        (57.0426, 9.9174),
    ]
    assert [point.point_timestamp for point in trajectory.points] == [
        datetime.datetime(2026, 9, 21, 8, 0, seconds) for seconds in (0, 15, 30, 45)
    ] + [datetime.datetime(2026, 9, 21, 8, 1)]


def test_loads_builder_routes_as_subpaths():
    """Load a multi-route builder fixture directly as similarity input."""
    fixture = Path(__file__).parent.parent / "data" / "trajectories" / "aalborg_germany.csv"

    subpaths = load_subpaths(fixture)

    assert len(subpaths) == 8
    assert [subpath.subpath_id for subpath in subpaths] == list(range(1, 9))
    assert [subpath.trajectory_id for subpath in subpaths] == list(range(1, 9))
    assert sum(len(subpath.points) for subpath in subpaths) == 198
    assert subpaths[0].exit_a_time == datetime.datetime(2026, 10, 6, 12, 46)
    assert subpaths[0].points[0].longitude == 9.909668
    assert subpaths[0].points[0].latitude == 57.043718
    for subpath in subpaths:
        assert subpath.exit_a_time == subpath.points[0].point_timestamp
        assert subpath.entry_b_time == subpath.points[-1].point_timestamp


def test_subpath_ids_preserve_explicit_ids_without_collisions(tmp_path):
    """Keep supplied trajectory IDs and give the other routes distinct local IDs."""
    fixture = tmp_path / "routes.csv"
    fixture.write_text(
        "trajectory_id,vehicle_id,vehicle_type,timestamp,longitude,latitude,city,source_id,database_trajectory_id\n"
        "route_a,0,UNKNOWN,2026-01-01 12:00:00,9,57,,,1\n"
        "route_a,0,UNKNOWN,2026-01-01 12:00:15,9.001,57,,,1\n"
        "route_b,0,UNKNOWN,2026-01-01 12:00:00,9,57,,,\n"
        "route_b,0,UNKNOWN,2026-01-01 12:00:15,9.002,57,,,\n",
        encoding="utf-8",
    )

    subpaths = load_subpaths(fixture)

    assert subpaths[0].trajectory_id == 1
    assert subpaths[1].trajectory_id == 2
