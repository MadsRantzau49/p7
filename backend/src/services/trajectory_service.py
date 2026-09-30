from datetime import date, time

from database.connection import create_db_connection
from database.queries import get_trajectories_cities_from_db, get_trajectories_from_db
from models.dataset import DataSet
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
