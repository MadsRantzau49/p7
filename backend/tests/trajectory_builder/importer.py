import datetime
import json
from pathlib import Path

from models.uniformed_trajectories import UniformedTrajectories, UniformedTrajectoryPoint
from models.upload_row import VehicleType


def load_trajectory(path: str | Path) -> UniformedTrajectories:
    with Path(path).open(encoding="utf-8") as fixture_file:
        data = json.load(fixture_file)

    if data.get("schema_version") != 1:
        raise ValueError("unsupported trajectory schema")

    start = datetime.datetime.fromisoformat(data["start_timestamp"].replace("Z", "+00:00"))
    interval = datetime.timedelta(seconds=data["interval_seconds"])
    points = [
        UniformedTrajectoryPoint(
            latitude=point["latitude"],
            longitude=point["longitude"],
            point_timestamp=start + index * interval,
        )
        for index, point in enumerate(data["points"])
    ]

    return UniformedTrajectories(
        vehicle_id=0,
        vehicle_type=VehicleType.UNKNOWN,
        trajectory_date=start,
        points=points,
        city="Test",
    )
