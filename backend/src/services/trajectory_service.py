from datetime import date, time

from database.connection import create_db_connection
from database.queries import (
    get_last_segmented_trajectory_id,
    get_trajectories_cities_from_db,
    get_trajectories_from_db,
    insert_segments_into_db,
    retrieve_cleaned_uniformed_batch,
)
from models.dataset import DataSet
from models.trajectory_segments import TrajectorySegments
from models.uniformed_trajectories import UniformedTrajectories


async def get_trajectories(
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
        raise ValueError("start_time must be before end_time when start_date and end_date are the same day")

    context = create_db_connection()

    try:
        # No timer filter if set at max
        if start_time == time(0, 0) and end_time is not None and end_time >= time(23, 59):
            start_time = None
            end_time = None

        return await get_trajectories_from_db(
            context,
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


async def insert_trajectory_segments(trajectories: list[dict]):
    """Creates segments from cleaned trajectory data"""

    segments = []

    context = create_db_connection()

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
        insert_segments_into_db(context, segments)
        context.commit()
        return len(segments)
    except Exception as error:
        print(f"Failed to insert trajectories segments: {error}")
        raise
    finally:
        context.close()


async def test_insert_trajectory_segments():
    """This function retrieves cleaned trajectories and inserts into segments"""
    batch_size = 100
    context = create_db_connection()
    try:
        last_id = get_last_segmented_trajectory_id(context)
        print(f"last_id: {last_id}")

        while True:
            current_batch = await retrieve_cleaned_uniformed_batch(context, batch_size, last_id)

            if not current_batch:
                break

            print(f"Retrieved {len(current_batch)} trajectories")

            for trajectory in current_batch:
                await insert_trajectory_segments([trajectory])
                last_id = trajectory["trajectory_id"]

                print(f"Inserted segments for trajectory_id {last_id}")
    except Exception as error:
        print(f"Failed to insert trajectory segments: {error}")
        context.rollback()
        raise
    finally:
        context.close()
