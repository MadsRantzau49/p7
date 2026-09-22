from datetime import datetime

from database.connection import create_db_connection
from database.queries import get_trajectories_from_db, get_trajectories_cities_from_db
from models.UniformedTrajectories import UniformedTrajectories


async def get_trajectories(city: str, start_date: datetime | None, end_date: datetime | None, limit: int | None) -> list[UniformedTrajectories]:
    context = create_db_connection()

    try:
        return await get_trajectories_from_db(context, city, start_date, end_date, limit)
    except Exception as error:
        print(f"Failed to get trajectories: {error}: Params: City: {city}, start_date: {start_date}, end_date: {end_date}, limit: {limit}")
        raise
    finally:
        context.close()

async def get_trajectories_cities():
    context = create_db_connection()
    
    try:
        return await get_trajectories_cities_from_db(context)
    
    except Exception as Error: 
        print(f"Failed to retrieve cities from database: {Error}")
        raise
    finally:
        context.close()