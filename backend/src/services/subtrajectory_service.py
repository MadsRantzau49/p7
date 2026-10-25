from datetime import date, datetime
from zoneinfo import ZoneInfo

from database.repositories.trajectory_repository import TrajectoryRepository
from helpers.boxes import make_box
from models.bounding_box import BoundingBox
from models.subtrajectory import Subtrajectory
from models.uniformed_trajectories import UniformedTrajectoryPoint


class SubtrajectoryService:
    def __init__(self, trajectory_repository: TrajectoryRepository) -> None:
        self.trajectory_repository = trajectory_repository

    def find_subtrajectories(
        self,
        a_longitude: float,
        a_latitude: float,
        b_longitude: float,
        b_latitude: float,
        start_date: date,
        end_date: date,
        box_half_width_m: float,
    ) -> list[Subtrajectory]:
        """Find the subtrajectories from location A to location B in the date range given."""
        if start_date > end_date:
            raise ValueError("start_date must be on or before end_date")
        if box_half_width_m <= 0:
            raise ValueError("box_half_width_m must be greater than 0")

        box_a = make_box(a_longitude, a_latitude, box_half_width_m)
        box_b = make_box(b_longitude, b_latitude, box_half_width_m)

        if box_a.intersects(box_b):
            raise ValueError("box A and box B must not overlap")

        rows = self.trajectory_repository.get_subtrajectories(
            BoundingBox(*box_a.bounds), BoundingBox(*box_b.bounds), start_date, end_date
        )

        subtrajectories = []

        for row in rows:
            zone = ZoneInfo(row["time_zone"])
            exit_a_time = row["exit_a_time"].astimezone(zone)
            entry_b_time = row["entry_b_time"].astimezone(zone)

            points = [UniformedTrajectoryPoint(row["exit_a_longitude"], exit_a_time, row["exit_a_latitude"])]

            for point in row["points_between"]:
                points.append(
                    UniformedTrajectoryPoint(
                        longitude=point["longitude"],
                        latitude=point["latitude"],
                        point_timestamp=datetime.fromisoformat(point["point_timestamp"]).astimezone(zone),
                    )
                )

            points.append(
                UniformedTrajectoryPoint(row["entry_b_longitude"], entry_b_time, row["entry_b_latitude"])
            )

            subtrajectories.append(
                Subtrajectory(
                    subtrajectory_id=len(subtrajectories) + 1,
                    trajectory_id=row["trajectory_id"],
                    exit_a_time=exit_a_time,
                    entry_b_time=entry_b_time,
                    points=points,
                )
            )

        return subtrajectories
