import sys
from datetime import datetime, time
from pathlib import Path

from fastapi import APIRouter

sys.path.append(str(Path(__file__).parent.parent))

from services.trajectory_service import get_trajectories, get_trajectories_cities

router = APIRouter(prefix="/api/trajectories")


@router.get("/get")
async def get_trajectories_endpoint(
    city: str,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    start_time: time | None = None,
    end_time: time | None = None,
    limit: int | None = None,
):
    """Return trajectories using the given filters."""
    return await get_trajectories(city, start_date, end_date, start_time,
        end_time, limit)


@router.get("/get/cities")
async def get_trajectories_cities_endpoint():
    """Return the available trajectory cities."""
    return await get_trajectories_cities()
