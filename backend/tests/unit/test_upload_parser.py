import io
from datetime import datetime

from helpers.upload_parser import EXPECTED_HEADER, MAX_ERRORS, parse_upload

HEADER = ",".join(EXPECTED_HEADER)


def parse(text: str):
    return parse_upload(io.StringIO(text, newline=""))


def test_rows_are_grouped_by_trajectory_id():
    trajectories, errors = parse(
        f"{HEADER}\n"
        "t1,7,CAR,2024-01-31 14:05:00,12.5,55.7\n"
        "t2,8,UNKNOWN,2024-01-31 09:00:00,10.0,56.0\n"
        "t1,7,CAR,2024-01-31 14:05:15,12.5,55.7\n"
    )

    assert errors == []
    assert list(trajectories) == ["t1", "t2"]
    assert [line for line, _ in trajectories["t1"]] == [2, 4]


def test_values_are_converted_to_real_types():
    trajectories, _ = parse(f"{HEADER}\nt1,7,CAR,2024-01-31 14:05:00,12.5,55.7\n")
    line, row = trajectories["t1"][0]

    assert line == 2
    assert row.vehicle_id == 7
    assert row.vehicle_type == "CAR"
    assert row.timestamp == datetime(2024, 1, 31, 14, 5)
    assert row.longitude == 12.5


def test_wrong_header_stops_parsing():
    trajectories, errors = parse("a,b,c\nt1,7,CAR,2024-01-31 14:05:00,12.5,55.7\n")

    assert trajectories == {}
    assert len(errors) == 1
    assert errors[0].line == 1


def test_empty_file_is_reported_as_a_header_problem():
    trajectories, errors = parse("")

    assert trajectories == {}
    assert len(errors) == 1


def test_blank_lines_are_ignored():
    trajectories, errors = parse(f"{HEADER}\n\nt1,7,CAR,2024-01-31 14:05:00,12.5,55.7\n\n")

    assert errors == []
    assert [line for line, _ in trajectories["t1"]] == [3]


def test_row_with_wrong_number_of_values():
    trajectories, errors = parse(f"{HEADER}\nt1,7,CAR\n")

    assert trajectories == {}
    assert errors[0].line == 2
    assert errors[0].message == "expected 6 values, got 3"


def test_every_invalid_field_is_reported():
    trajectories, errors = parse(f"{HEADER}\nt1,-1,car,2024-01-31,12.5,95\n")

    assert trajectories == {}
    assert len(errors) == 4
    assert all(error.line == 2 for error in errors)


def test_parsing_stops_after_the_error_limit():
    _, errors = parse(f"{HEADER}\n" + "t1,7,CAR,2024-01-31 14:05:00,12.5,95\n" * 500)

    assert len(errors) <= MAX_ERRORS + 1
    assert errors[-1].message == f"stopped after {MAX_ERRORS} errors"
