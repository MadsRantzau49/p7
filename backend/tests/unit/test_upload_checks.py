import io

from helpers.upload_checks import MAX_SPEED_KMH, sort_and_check_trajectories
from helpers.upload_parser import EXPECTED_HEADER, parse_upload

HEADER = ",".join(EXPECTED_HEADER)

COPENHAGEN = "12.5683,55.6761"
AARHUS = "10.2039,56.1629"

def check(rows_text: str):
    trajectories, errors = parse_upload(io.StringIO(f"{HEADER}\n{rows_text}", newline=""))
    assert errors == []
    return trajectories, sort_and_check_trajectories(trajectories)


def test_a_valid_trajectory_has_no_errors():
    trajectories, errors = check(
        "t1,7,CAR,2024-01-31 14:05:00,12.500,55.700\n"
        "t1,7,CAR,2024-01-31 14:05:30,12.502,55.700\n"
    )

    assert errors == []


def test_points_are_sorted_by_timestamp():
    trajectories, errors = check(
        "t1,7,CAR,2024-01-31 14:05:30,12.502,55.700\n"
        "t1,7,CAR,2024-01-31 14:05:00,12.500,55.700\n"
    )

    assert [line for line, _ in trajectories["t1"]] == [3, 2]


def test_one_point_is_not_a_trajectory():
    trajectories, errors = check("t1,7,CAR,2024-01-31 14:05:00,12.5,55.7\n")

    assert len(errors) == 1
    assert "needs at least 2" in errors[0].message


def test_the_vehicle_may_not_change():
    trajectories, errors = check(
        "t1,7,CAR,2024-01-31 14:05:00,12.5,55.7\n"
        "t1,8,CAR,2024-01-31 14:05:10,12.5,55.7\n"
        "t1,7,UNKNOWN,2024-01-31 14:05:20,12.5,55.7\n"
    )

    assert [error.line for error in errors] == [3, 4]


def test_two_points_may_not_share_a_timestamp():
    trajectories, errors = check(
        "t1,7,CAR,2024-01-31 14:05:00,12.5,55.7\n"
        "t1,7,CAR,2024-01-31 14:05:00,12.5,55.7\n"
    )

    assert len(errors) == 1
    assert "same timestamp as line 2" in errors[0].message


def test_moving_too_fast_is_rejected():
    trajectories, errors = check(
        f"t1,7,CAR,2024-01-31 14:00:00,{COPENHAGEN}\n"
        f"t1,7,CAR,2024-01-31 14:10:00,{AARHUS}\n"
    )

    assert len(errors) == 1
    assert f"max is {MAX_SPEED_KMH}" in errors[0].message


def test_the_same_journey_at_a_realistic_speed_is_accepted():
    trajectories, errors = check(
        f"t1,7,CAR,2024-01-31 14:00:00,{COPENHAGEN}\n"
        f"t1,7,CAR,2024-01-31 16:00:00,{AARHUS}\n"
    )

    assert errors == []


def test_each_trajectory_is_checked_on_its_own():
    trajectories, errors = check(
        "t1,7,CAR,2024-01-31 14:05:00,12.5,55.7\n"
        "t2,8,CAR,2024-01-31 14:05:00,12.5,55.7\n"
        "t1,7,CAR,2024-01-31 14:05:30,12.5,55.7\n"
        "t2,8,CAR,2024-01-31 14:05:30,12.5,55.7\n"
    )

    assert errors == []