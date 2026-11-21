from datetime import datetime, time
from zoneinfo import ZoneInfo

from database.repositories.trajectory_repository import TrajectoryRepository
from models.bounding_box import BoundingBox
from models.date_range import DateRange
from models.subtrajectory import Subtrajectory
from models.uniformed_trajectories import UniformedTrajectoryPoint


class SubtrajectoryService:
    def __init__(self, trajectory_repository: TrajectoryRepository) -> None:
        self.trajectory_repository = trajectory_repository

    def find_subtrajectories(
        self,
        box_a: BoundingBox,
        box_b: BoundingBox,
        dates: DateRange,
        start_time: time | None = None,
        end_time: time | None = None,
    ) -> list[Subtrajectory]:
        """Find the subtrajectories between two bounding boxes in the date range given.
        start_time and end_time is optional, since users might not need to look at specific time periods.
        the start_time indicates when a trajectory has left the start area and wise versa for end_time.
        """
        dates.validate()
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
            box_a, box_b, dates.start_date, dates.end_date, start_time, end_time
        )

        subtrajectories = []

        for row in rows:
            zone = ZoneInfo(row["time_zone"])
            exit_a_time = row["exit_a_time"].astimezone(zone)
            entry_b_time = row["entry_b_time"].astimezone(zone)

            if not dates.contains(exit_a_time.date()):
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
