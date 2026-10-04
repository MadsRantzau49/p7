import pytest
from helpers import parsers


def test_parse_porto_trajectories(tmp_path):
    """Parse a Porto CSV row into a trajectory."""
    path = tmp_path / "porto.csv"
    path.write_text(
        "TRIP_ID,CALL_TYPE,ORIGIN_CALL,ORIGIN_STAND,TAXI_ID,TIMESTAMP,DAY_TYPE,MISSING_DATA,POLYLINE\n"
        '1,,,,2,3,,true,"[[1, 2]]"\n'
    )

    result = parsers.parse_porto_trajectories(str(path))

    assert len(result) == 1
    assert result[0].missing_data is True
    assert result[0].polyline == [[1, 2]]


def test_parse_beijing_trajectories(tmp_path):
    """Split Beijing points when their time gap exceeds 30 minutes."""
    (tmp_path / "taxi.txt").write_text(
        "1,2024-01-01 00:00:00,1,2\n"
        "1,2024-01-01 00:31:00,3,4\n"
    )

    result = parsers.parse_beijing_trajectories(str(tmp_path))

    assert len(result) == 2
    assert result[0].points[0].longitude == "1"
    assert result[1].points[0].longitude == "3"


def test_parse_beijing_rejects_missing_taxi_id(tmp_path, monkeypatch):
    """Reject a completed Beijing trajectory without a taxi ID."""
    (tmp_path / "taxi.txt").write_text("1,2024-01-01 00:00:00,1,2\n")
    monkeypatch.setattr(parsers, "int", lambda value: None, raising=False)

    with pytest.raises(ValueError, match="Taxi ID is missing"):
        parsers.parse_beijing_trajectories(str(tmp_path))
