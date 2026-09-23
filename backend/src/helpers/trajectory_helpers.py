import json, uuid, sys
from pathlib import Path

from models.upload_row import VehicleType, UploadRow

sys.path.append(str(Path(__file__).parent.parent))

from models.UniformedTrajectories import UniformedTrajectoryPoint, UniformedTrajectories
from models.porto_trajectory import porto_trajectory
from datetime import datetime, timedelta


def create_uuid_key():
    return str(uuid.uuid4())

def convert_porto_trajectory(porto_trajectory: dict) -> UniformedTrajectories:
    polyline = porto_trajectory["polyline"]

    while isinstance(polyline, str):
        polyline = json.loads(polyline)

    start_time = datetime.fromtimestamp(
        int(porto_trajectory["timestamp"])
    )

    current_time = start_time
    points = []

    for longitude, latitude in polyline:
        points.append(UniformedTrajectoryPoint(longitude=float(longitude), latitude=float(latitude), point_timestamp=current_time))

        current_time += timedelta(seconds=15) # Stated on kaggle, each point is recorded after 15 seconds from the start, so we need to keep track of the time.

    return UniformedTrajectories(
        vehicle_id=porto_trajectory["taxi_id"],
        vehicle_type=VehicleType.TAXI,
        trajectory_date=datetime.fromtimestamp(porto_trajectory["timestamp"]),
        points=points,
        city="Porto",
        source_id=porto_trajectory["source_id"]
    )

def convert_beijing_trajectory(beijing_trajectory: dict) -> UniformedTrajectories:
    beijing_points = beijing_trajectory["points"]

    while isinstance(beijing_points, str):
        beijing_points = json.loads(beijing_points)

    points = []
    
    for point in beijing_points:
        point_datetime = datetime.strptime(
            point["date_time"],
            "%Y-%m-%d %H:%M:%S"
        )

        points.append(
            UniformedTrajectoryPoint(
                longitude=float(point["longitude"]),
                latitude=float(point["latitude"]),
                point_timestamp=point_datetime
            )
        )

    first_datetime = datetime.strptime(beijing_points[0]["date_time"], "%Y-%m-%d %H:%M:%S")

    return UniformedTrajectories(
        vehicle_id=int(beijing_trajectory["taxi_id"]),
        vehicle_type=VehicleType.TAXI,
        trajectory_date=first_datetime, 
        city="Beijing", 
        source_id=beijing_trajectory["source_id"],
        points=points
        )

def convert_upload_trajectory(rows: list[tuple[int, UploadRow]], city: str) -> UniformedTrajectories:
    """Convert one uploaded trajectory into the uniform model

    Args:
        rows: The trajectory's points as (line number, row) pairs.
        city: The dataset's name, which uploads as their city.

    Returns:
        The trajectory, with a new source_id for the source_trajectories table.
    """
    points = []

    for line, row in rows:
        points.append(UniformedTrajectoryPoint(
            longitude=row.longitude,
            latitude=row.latitude,
            point_timestamp=row.timestamp,
        ))

    first_line, first_row = rows[0]

    return UniformedTrajectories(
        vehicle_id=first_row.vehicle_id,
        vehicle_type=first_row.vehicle_type,
        trajectory_date=first_row.timestamp,
        city=city,
        points=points,
        source_id=str(uuid.uuid4()),
    )