from datetime import datetime

from database.connection import create_db_connection
from database.queries import (
    get_trajectories_cities_from_db,
    get_trajectories_from_db,
    insert_segments_into_db,
)
from models.dataset import DataSet
from models.trajectory_segments import TrajectorySegments
from models.uniformed_trajectories import UniformedTrajectories


async def get_trajectories(
    city: str, start_date: datetime | None, end_date: datetime | None, limit: int | None
) -> list[UniformedTrajectories]:
    """Fetch trajectories from the database using the given filters."""
    context = create_db_connection()

    try:
        return await get_trajectories_from_db(context, city, start_date, end_date, limit)
    except Exception as error:
        print(
            f"Failed to get trajectories: {error}: "
            f"Params: City: {city}, start_date: {start_date}, "
            f"end_date: {end_date}, limit: {limit}"
        )
        raise
    finally:
        context.close()


async def get_trajectories_cities() -> list[DataSet]:
    """Fetch the available trajectory cities from the database."""
    context = create_db_connection()

    try:
        return await get_trajectories_cities_from_db(context)

    except Exception as error:
        print(f"Failed to retrieve cities from database: {error}")
        raise
    finally:
        context.close()


def insert_trajectory_segments(trajectories: list[UniformedTrajectories]):
    """Creates segments from cleaned trajectory data"""
    rows = []
    segments: list[TrajectorySegments] = []

    context = create_db_connection()

    for trajectory in trajectories:
        points = trajectory.points

        for segment_index in range(len(points) - 1):
            start = points[segment_index]
            end = points[segment_index + 1]

            path = f"LINESTRING({start.longitude} {start.latitude}, {end.longitude} {end.latitude})"

            if trajectory.trajectory_id is None:
                raise ValueError("Trajectory_id is none!")

            segments.append(
                TrajectorySegments(
                    trajectory_id=trajectory.trajectory_id,
                    segment_index=segment_index,
                    path=path,
                    start_time=start.point_timestamp,
                    end_time=end.point_timestamp,
                )
            )

    if not rows:
        return 0

    try:
        insert_segments_into_db(context, rows)
        context.commit()
        return len(rows)
    except Exception as error:
        print(f"Failed to insert trajectories segments: {error}")
        raise
    finally:
        context.close()
