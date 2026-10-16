from datetime import date, time

from database.database_actions import DatabaseActions
from database.repositories.dataset_repository import DatasetRepository
from database.repositories.trajectory_repository import TrajectoryRepository
from models.dataset import DataSet
from models.trajectory_segments import TrajectorySegments
from models.uniformed_trajectories import UniformedTrajectories


class TrajectoryService:
    def __init__(
        self,
        trajectory_repository: TrajectoryRepository,
        dataset_repository: DatasetRepository,
        db_actions: DatabaseActions,
    ) -> None:
        self.trajectory_repository = trajectory_repository
        self.dataset_repository = dataset_repository
        self.db_actions = db_actions

    async def get_trajectories(
        self,
        city: str,
        start_date: date | None,
        end_date: date | None,
        start_time: time | None,
        end_time: time | None,
        limit: int | None,
    ) -> list[UniformedTrajectories]:
        """Fetch trajectories from the database using the given filters."""

        if start_date is not None and end_date is not None and start_date > end_date:
            raise ValueError("start_date must be before end_date")

        same_day = start_date is not None and end_date is not None and start_date == end_date

        if same_day and start_time is not None and end_time is not None and start_time > end_time:
            raise ValueError(
                "start_time must be before end_time when start_date and end_date are the same day"
            )

        try:
            # No timer filter if set at max
            if start_time == time(0, 0) and end_time is not None and end_time >= time(23, 59):
                start_time = None
                end_time = None

            return await self.trajectory_repository.get_trajectories_from_db(
                city,
                start_date,
                end_date,
                start_time,
                end_time,
                limit,
            )

        except Exception as error:
            print(
                f"Failed to get trajectories: {error}: "
                f"Params: city={city}, "
                f"start_date={start_date}, "
                f"end_date={end_date}, "
                f"start_time={start_time}, "
                f"end_time={end_time}, "
                f"limit={limit}"
            )
            raise

    async def get_trajectories_cities(self) -> list[DataSet]:
        """Fetch the available trajectory cities from the database."""

        try:
            return await self.dataset_repository.get_trajectories_cities_from_db()

        except Exception as error:
            print(f"Failed to retrieve cities from database: {error}")
            raise

    async def insert_trajectory_segments(self, trajectories: list[dict]):
        """Creates segments from cleaned trajectory data"""

        segments = []

        for trajectory in trajectories:
            points = trajectory["points"]

            for segment_index in range(len(points) - 1):
                start = points[segment_index]
                end = points[segment_index + 1]

                start_lon = start["longitude"]
                start_lat = start["latitude"]
                end_lon = end["longitude"]
                end_lat = end["latitude"]

                path = f"LINESTRING({start_lon} {start_lat}, {end_lon} {end_lat})"

                if trajectory["trajectory_id"] is None:
                    raise ValueError("Trajectory_id is none!")

                segments.append(
                    TrajectorySegments(
                        trajectory_id=trajectory["trajectory_id"],
                        segment_index=segment_index,
                        path=path,
                        start_time=start["point_timestamp"],
                        end_time=end["point_timestamp"],
                    )
                )

        if not segments:
            return 0

        try:
            self.trajectory_repository.insert_segments_into_db(segments)
            self.db_actions.commit()
            return len(segments)
        except Exception as error:
            print(f"Failed to insert trajectories segments: {error}")
            self.db_actions.rollback()
            raise
