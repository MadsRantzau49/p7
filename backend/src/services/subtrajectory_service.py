from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from database.repositories.trajectory_repository import TrajectoryRepository
from models.bounding_box import BoundingBox
from models.subtrajectory import Subtrajectory
from models.uniformed_trajectories import UniformedTrajectoryPoint


class SubtrajectoryService:
    def __init__(self, trajectory_repository: TrajectoryRepository) -> None:
        self.trajectory_repository = trajectory_repository

    def find_subtrajectories(
        self,
        box_a: BoundingBox,
        box_b: BoundingBox,
        start_date: date | None = None,
        end_date: date | None = None,
        start_time: time | None = None,
        end_time: time | None = None,
    ) -> list[Subtrajectory]:
        """Find passages between two rectangles, optionally filtering local departure dates and hours."""
        if start_date is not None and end_date is not None and start_date > end_date:
            raise ValueError("start_date must be on or before end_date")
        if any(
            area.min_longitude >= area.max_longitude or area.min_latitude >= area.max_latitude
            for area in (box_a, box_b)
        ):
            raise ValueError("Each area must have minimum coordinates smaller than maximum coordinates")

        if (
            box_a.min_longitude <= box_b.max_longitude
            and box_a.max_longitude >= box_b.min_longitude
            and box_a.min_latitude <= box_b.max_latitude
            and box_a.max_latitude >= box_b.min_latitude
        ):
            raise ValueError("box A and box B must not overlap")

        rows = self.trajectory_repository.get_subtrajectories(
            box_a, box_b, start_date, end_date, start_time, end_time
        )

        subtrajectories = []

        for row in rows:
            zone = ZoneInfo(row["time_zone"])
            exit_a_time = row["exit_a_time"].astimezone(zone)
            entry_b_time = row["entry_b_time"].astimezone(zone)

            if (start_date is not None and exit_a_time.date() < start_date) or (
                end_date is not None and exit_a_time.date() > end_date
            ):
                continue

            points = [UniformedTrajectoryPoint(row["exit_a_longitude"], exit_a_time, row["exit_a_latitude"])]

            for point in row["points"]:
                point_timestamp = datetime.fromisoformat(point["point_timestamp"]).astimezone(zone)

                if exit_a_time < point_timestamp < entry_b_time:
                    points.append(
                        UniformedTrajectoryPoint(
                            longitude=point["longitude"],
                            latitude=point["latitude"],
                            point_timestamp=point_timestamp,
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
