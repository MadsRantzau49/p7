from datetime import date
from typing import Annotated

from dependencies import get_subtrajectory_service
from fastapi import APIRouter, Depends, HTTPException
from models.subtrajectory import Subtrajectory
from services.subtrajectory_service import SubtrajectoryService

router = APIRouter(prefix="/api/subtrajectories")


@router.get("/get", response_model=list[Subtrajectory])
def get_subtrajectories(
    service: Annotated[SubtrajectoryService, Depends(get_subtrajectory_service)],
    a_longitude: float,
    a_latitude: float,
    b_longitude: float,
    b_latitude: float,
    start_date: date,
    end_date: date,
    box_half_width_m: float = 50,
):
    """Return the subtrajectories from location A to location B in the date range given."""
    try:
        return service.find_subtrajectories(
            a_longitude, a_latitude, b_longitude, b_latitude, start_date, end_date, box_half_width_m
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
