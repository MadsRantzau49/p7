from datetime import UTC, date, datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest
from services.subtrajectory_service import SubtrajectoryService

LISBON = ZoneInfo("Europe/Lisbon")


def make_row():
    """One row as get_subtrajectories returns it, with times in UTC."""
    return {
        "trajectory_id": 7,
        "exit_a_time": datetime(2013, 7, 1, 8, 10, 48, tzinfo=UTC),
        "entry_b_time": datetime(2013, 7, 1, 8, 12, 12, tzinfo=UTC),
        "exit_a_longitude": -8.612,
        "exit_a_latitude": 41.15,
        "entry_b_longitude": -8.598,
        "entry_b_latitude": 41.15,
        "points_between": [
            {"longitude": -8.61, "latitude": 41.15, "point_timestamp": "2013-07-01T08:11:00+00:00"},
            {"longitude": -8.60, "latitude": 41.15, "point_timestamp": "2013-07-01T08:12:00+00:00"},
        ],
        "time_zone": "Europe/Lisbon",
    }


def test_find_subtrajectories():
    """Build each subtrajectory from the exit, the points in between and the entry, in local time."""
    repository = MagicMock()
    repository.get_subtrajectories.return_value = [make_row()]

    [found] = SubtrajectoryService(repository).find_subtrajectories(
        -8.614, 41.15, -8.596, 41.15, date(2013, 7, 1), date(2013, 7, 2), 50
    )

    box_a, box_b, start_date, end_date = repository.get_subtrajectories.call_args.args
    # Each box is centred on its location
    assert (box_a.min_longitude + box_a.max_longitude) / 2 == pytest.approx(-8.614)
    assert (box_a.min_latitude + box_a.max_latitude) / 2 == pytest.approx(41.15)
    assert (box_b.min_longitude + box_b.max_longitude) / 2 == pytest.approx(-8.596)
    assert (start_date, end_date) == (date(2013, 7, 1), date(2013, 7, 2))

    assert found.subtrajectory_id == 1
    assert found.trajectory_id == 7
    assert found.exit_a_time == datetime(2013, 7, 1, 9, 10, 48, tzinfo=LISBON)
    assert found.exit_a_time.tzinfo == LISBON
    assert [point.longitude for point in found.points] == [-8.612, -8.61, -8.60, -8.598]
    assert all(point.point_timestamp.tzinfo == LISBON for point in found.points)


@pytest.mark.parametrize(
    ("b_longitude", "start_date", "end_date", "half_width_m", "message"),
    [
        (-8.596, date(2013, 7, 2), date(2013, 7, 1), 50, "start_date must be on or before end_date"),
        (-8.596, date(2013, 7, 1), date(2013, 7, 1), 0, "box_half_width_m must be greater than 0"),
        (-8.6141, date(2013, 7, 1), date(2013, 7, 1), 50, "box A and box B must not overlap"),
    ],
)
def test_find_subtrajectories_rejects_invalid_input(b_longitude, start_date, end_date, half_width_m, message):
    """Reject reversed dates, empty boxes and overlapping boxes before querying."""
    repository = MagicMock()

    with pytest.raises(ValueError, match=message):
        SubtrajectoryService(repository).find_subtrajectories(
            -8.614, 41.15, b_longitude, 41.15, start_date, end_date, half_width_m
        )

    repository.get_subtrajectories.assert_not_called()
