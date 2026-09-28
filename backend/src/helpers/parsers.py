import csv
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from datetime import datetime, timedelta

from models.beijing_trajectory import BeijingTrajectory, TrajectoryPoint
from models.porto_trajectory import PortoTrajectory

MAX_TIME_GAP = timedelta(minutes=30)


def parse_beijing_trajectories(file_path: str):
    """
    Retrieves trajectory data from the beijing dataset and saves to db
    Beijing dataset consists of individual txt files
    Important to note that a single txt file contains multiple paths from different dates for a specific taxi
    """
    dataset_folder = Path(file_path)
    trajectories = []

    for trajectory_file in dataset_folder.iterdir():
        trajectory_points = []
        previous_time = None
        taxi_id = None

        with open(trajectory_file, encoding="utf-8") as file:
            for line in file:
                values = line.strip().split(",")

                taxi_id = int(values[0])

                current_time = datetime.strptime(values[1], "%Y-%m-%d %H:%M:%S")

                point = TrajectoryPoint(date_time=values[1], longitude=values[2], latitude=values[3])

                if previous_time is not None:
                    date_changed = current_time.date() != previous_time.date()

                    gap_too_large = current_time - previous_time > MAX_TIME_GAP

                    if date_changed or gap_too_large:
                        trajectory = BeijingTrajectory(taxi_id=taxi_id, points=trajectory_points)

                        trajectories.append(trajectory)

                        trajectory_points = []

                trajectory_points.append(point)

                previous_time = current_time

        if trajectory_points:
            if taxi_id is None:
                raise ValueError("Taxi ID is missing")
            trajectory = BeijingTrajectory(taxi_id=taxi_id, points=trajectory_points)

            trajectories.append(trajectory)

    return trajectories


def parse_porto_trajectories(file_path: str) -> list[PortoTrajectory]:
    """Maps dataset to porto_trajectories object and returns a list containing all trajectories"""
    trajectories = []

    with open(file_path) as csv_file:
        reader = csv.DictReader(csv_file)

        for row in reader:
            trajectory = PortoTrajectory(
                trip_id=int(row["TRIP_ID"]),
                call_type=row["CALL_TYPE"] or None,
                origin_call=row["ORIGIN_CALL"] or None,
                origin_stand=row["ORIGIN_STAND"] or None,
                taxi_id=int(row["TAXI_ID"]),
                timestamp=int(row["TIMESTAMP"]),
                day_type=row["DAY_TYPE"] or None,
                missing_data=row["MISSING_DATA"].strip().lower() == "true",
                polyline=json.loads(row["POLYLINE"]),
            )

            trajectories.append(trajectory)

    return trajectories
