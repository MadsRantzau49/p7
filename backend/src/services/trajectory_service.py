from datetime import datetime, time

from database.connection import create_db_connection
from database.queries import get_trajectories_cities_from_db, get_trajectories_from_db
from models.dataset import DataSet
from models.uniformed_trajectories import UniformedTrajectories


async def get_trajectories(
    city: str,
    start_date: datetime | None,
    end_date: datetime | None,
    start_time: time | None,
    end_time: time | None,
    limit: int | None,
) -> list[UniformedTrajectories]:
    """Fetch trajectories from the database using the given filters."""

    context = create_db_connection()

    try:
        # No time = 24 hours
        start_time = start_time or time.min
        end_time = end_time or time.max
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
