import sys
from datetime import date, time
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

sys.path.append(str(Path(__file__).parent.parent))

from dependencies import get_trajectory_service
from services.trajectory_service import TrajectoryService

router = APIRouter(prefix="/api/trajectories")


@router.get("/get")
async def get_trajectories_endpoint(
    service: Annotated[TrajectoryService, Depends(get_trajectory_service)],
    city: str,
    start_date: date | None = None,
    end_date: date | None = None,
    start_time: time | None = None,
    end_time: time | None = None,
    limit: int | None = None,
):
    """Return trajectories using the given filters."""
    try:
        return await service.get_trajectories(city, start_date, end_date, start_time, end_time, limit)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/get/cities")
def get_trajectories_cities_endpoint(
    service: Annotated[TrajectoryService, Depends(get_trajectory_service)],
):
    """Return the available trajectory cities."""
    return service.get_trajectories_cities()
