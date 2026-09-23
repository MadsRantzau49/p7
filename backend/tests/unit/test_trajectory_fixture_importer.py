import datetime
from pathlib import Path

from trajectory_builder.importer import load_trajectory


def test_imports_template_and_generates_timestamps():
    fixture = Path(__file__).parent.parent / "data" / "trajectories" / "template.json"

    trajectory = load_trajectory(fixture)

    assert trajectory.trajectory_id is None
    assert trajectory.trajectory_date == datetime.datetime(2026, 9, 21, 8, 0, tzinfo=datetime.timezone.utc)
    assert [(point.latitude, point.longitude) for point in trajectory.points] == [
        (57.0252, 9.8981),
        (57.0294, 9.9018),
        (57.0337, 9.9062),
        (57.0381, 9.9116),
        (57.0426, 9.9174),
    ]
    assert [point.point_timestamp for point in trajectory.points] == [
        datetime.datetime(2026, 9, 21, 8, 0, seconds, tzinfo=datetime.timezone.utc)
        for seconds in (0, 15, 30, 45)
    ] + [datetime.datetime(2026, 9, 21, 8, 1, tzinfo=datetime.timezone.utc)]
