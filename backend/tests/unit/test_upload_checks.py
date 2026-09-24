import io

import pytest
from helpers.upload_checks import sort_and_check_trajectories, speed_kmh
from helpers.upload_parser import EXPECTED_HEADER, parse_upload

HEADER = ",".join(EXPECTED_HEADER)

COPENHAGEN = "12.5683,55.6761"
AARHUS = "10.2039,56.1629"


def check(rows_text: str):
    """Parse and validate trajectory rows for testing."""
    trajectories, errors = parse_upload(io.StringIO(f"{HEADER}\n{rows_text}", newline=""))
    assert errors == []
    return trajectories, sort_and_check_trajectories(trajectories)


def test_a_valid_trajectory_has_no_errors():
    """Check valid trajectories have no errors"""
    trajectories, errors = check(
        "t1,7,CAR,2024-01-31 14:05:00,12.500,55.700\nt1,7,CAR,2024-01-31 14:05:30,12.502,55.700\n"
    )

    assert errors == []


def test_points_are_sorted_by_timestamp():
    """Check tests points are sorted by timestamp"""
    trajectories, errors = check(
        "t1,7,CAR,2024-01-31 14:05:30,12.502,55.700\nt1,7,CAR,2024-01-31 14:05:00,12.500,55.700\n"
    )

    assert [line for line, _ in trajectories["t1"]] == [3, 2]


def test_one_point_is_not_a_trajectory():
    """Check one point is not a trajectory"""
    trajectories, errors = check("t1,7,CAR,2024-01-31 14:05:00,12.5,55.7\n")

    assert len(errors) == 1
    assert "needs at least 2" in errors[0].message


def test_the_vehicle_may_not_change():
    """Check the vehicle may not change type"""
    trajectories, errors = check(
        "t1,7,CAR,2024-01-31 14:05:00,12.5,55.7\n"
        "t1,8,CAR,2024-01-31 14:05:10,12.5,55.7\n"
        "t1,7,UNKNOWN,2024-01-31 14:05:20,12.5,55.7\n"
    )

    assert [error.line for error in errors] == [3, 4]


def test_two_points_may_not_share_a_timestamp():
    """Check that two points cannot have the same timestamp."""
    trajectories, errors = check(
        "t1,7,CAR,2024-01-31 14:05:00,12.5,55.7\nt1,7,CAR,2024-01-31 14:05:00,12.5,55.7\n"
    )

    assert len(errors) == 1
    assert "same timestamp as line 2" in errors[0].message


def test_moving_too_fast_is_accepted():
    """Check that very high movement speed is still accepted."""
    trajectories, errors = check(
        f"t1,7,CAR,2024-01-31 14:00:00,{COPENHAGEN}\nt1,7,CAR,2024-01-31 14:10:00,{AARHUS}\n"
    )

    assert errors == []


def test_speed_is_distance_divided_by_time():
    """Check that speed is calculated as distance divided by time."""
    trajectories, errors = check(
        f"t1,7,CAR,2024-01-31 14:00:00,{COPENHAGEN}\nt1,7,CAR,2024-01-31 16:00:00,{AARHUS}\n"
    )
    (_, copenhagen), (_, aarhus) = trajectories["t1"]

    assert speed_kmh(copenhagen, aarhus) == pytest.approx(157 / 2, abs=1)


def test_speed_with_the_same_timestamp_raises():
    """Check that calculating speed with the same timestamp raises an error."""
    trajectories, errors = check(
        "t1,7,CAR,2024-01-31 14:00:00,12.5,55.7\nt1,7,CAR,2024-01-31 14:00:00,12.6,55.7\n"
    )
    (_, first), (_, second) = trajectories["t1"]

    with pytest.raises(ZeroDivisionError):
        speed_kmh(first, second)


def test_each_trajectory_is_checked_on_its_own():
    """Check that each trajectory is validated independently."""
    trajectories, errors = check(
        "t1,7,CAR,2024-01-31 14:05:00,12.5,55.7\n"
        "t2,8,CAR,2024-01-31 14:05:00,12.5,55.7\n"
        "t1,7,CAR,2024-01-31 14:05:30,12.5,55.7\n"
        "t2,8,CAR,2024-01-31 14:05:30,12.5,55.7\n"
    )

    assert errors == []
