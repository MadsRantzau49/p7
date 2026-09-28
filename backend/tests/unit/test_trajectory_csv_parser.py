import io
from datetime import datetime

import pytest
from helpers.trajectory_csv_parser import InvalidTrajectoryCsvError, parse_trajectory_csv
from helpers.upload_parser import EXPECTED_HEADER
from models.upload_row import VehicleType

HEADER = ",".join(EXPECTED_HEADER)


def test_parses_valid_csv_into_uniformed_trajectories():
    """Check CSV parsing returns complete, sorted uniformed models."""
    csv_data = io.StringIO(
        f"{HEADER}\n"
        "route-a,7,CAR,2024-01-31 14:05:30,12.6,55.8,Copenhagen,source-a,42\n"
        "route-b,8,TAXI,2024-01-31 09:00:00,10.0,56.0,Aarhus,,\n"
        "route-a,7,CAR,2024-01-31 14:05:00,12.5,55.7,Copenhagen,source-a,42\n"
        "route-b,8,TAXI,2024-01-31 09:00:15,10.1,56.1,Aarhus,,\n",
        newline="",
    )

    trajectories = parse_trajectory_csv(csv_data)

    assert len(trajectories) == 2
    first = trajectories[0]
    assert first.vehicle_id == 7
    assert first.vehicle_type is VehicleType.CAR
    assert first.trajectory_date == datetime(2024, 1, 31, 14, 5)
    assert first.trajectory_id == 42
    assert first.city == "Copenhagen"
    assert first.source_id == "source-a"
    assert [point.point_timestamp for point in first.points] == [
        datetime(2024, 1, 31, 14, 5),
        datetime(2024, 1, 31, 14, 5, 30),
    ]
    assert trajectories[1].trajectory_id is None
    assert trajectories[1].source_id is None


def test_invalid_csv_raises_with_line_errors():
    """Check callers receive the same detailed validation errors as uploads."""
    csv_data = io.StringIO(
        f"{HEADER}\nroute-a,7,CAR,2024-01-31 14:05:00,12.5,55.7,,,\n",
        newline="",
    )

    with pytest.raises(InvalidTrajectoryCsvError) as raised:
        parse_trajectory_csv(csv_data)

    assert raised.value.errors[0].line == 2
    assert "needs at least 2" in raised.value.errors[0].message
