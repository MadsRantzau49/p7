import sys
from pathlib import Path

from models.beijing_trajectory import BeijingTrajectory
from models.porto_trajectory import PortoTrajectory
from models.uniformed_trajectories import VehicleType

sys.path.append(str(Path(__file__).parent.parent))
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from models.uniformed_trajectories import UniformedTrajectories, UniformedTrajectoryPoint

BEIJING_TIME_ZONE = ZoneInfo("Asia/Shanghai")


def convert_porto_trajectory(porto_trajectory: PortoTrajectory) -> UniformedTrajectories:
    """Convert a Porto trajectory to the uniform trajectory format."""
    start_time = datetime.fromtimestamp(porto_trajectory.timestamp, UTC)

    current_time = start_time
    points = []

    for longitude, latitude in porto_trajectory.polyline:
        points.append(
            UniformedTrajectoryPoint(
                longitude=float(longitude), latitude=float(latitude), point_timestamp=current_time
            )
        )
        # Stated on kaggle, each point is recorded after 15 seconds from the start,
        # so we need to keep track of the time.
        current_time += timedelta(seconds=15)

    return UniformedTrajectories(
        vehicle_id=str(porto_trajectory.taxi_id),
        vehicle_type=VehicleType.TAXI,
        trajectory_date=start_time,
        points=points,
        city="Porto",
    )


def convert_beijing_trajectory(beijing_trajectory: BeijingTrajectory) -> UniformedTrajectories:
    """Convert a Beijing trajectory to the uniform trajectory format."""
    points = []

    for point in beijing_trajectory.points:
        point_datetime = datetime.strptime(point.date_time, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=BEIJING_TIME_ZONE
        )

        points.append(
            UniformedTrajectoryPoint(
                longitude=float(point.longitude),
                latitude=float(point.latitude),
                point_timestamp=point_datetime,
            )
        )

    return UniformedTrajectories(
        vehicle_id=str(beijing_trajectory.taxi_id),
        vehicle_type=VehicleType.TAXI,
        trajectory_date=points[0].point_timestamp,
        city="Beijing",
        points=points,
    )
