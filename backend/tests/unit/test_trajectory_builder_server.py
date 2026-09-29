from pathlib import Path

import pytest
from trajectory_builder import server


def test_save_fixture_writes_csv_and_uses_an_available_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Check builder fixtures are saved as CSV without overwriting files."""
    monkeypatch.setattr(server, "DATA_DIRECTORY", tmp_path)
    csv_data = "trajectory_id,vehicle_id\nroute,0\n"

    first = server.save_fixture("route", csv_data)
    second = server.save_fixture("route", csv_data)

    assert first.name == "route.csv"
    assert second.name == "route_2.csv"
    assert first.read_text(encoding="utf-8") == csv_data


def test_save_fixture_rejects_unsafe_names(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Check fixture names cannot write outside the data directory."""
    monkeypatch.setattr(server, "DATA_DIRECTORY", tmp_path)

    with pytest.raises(ValueError):
        server.save_fixture("../route", "csv")


def test_fixture_name_is_read_from_csv():
    """Check saving does not depend on a separate query-string name."""
    csv_data = "trajectory_id,vehicle_id\nroute,0\n"

    assert server.fixture_name_from_csv(csv_data) == "route"
