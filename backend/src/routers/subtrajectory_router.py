from datetime import date
from typing import Annotated

from dependencies import get_subtrajectory_service
from fastapi import APIRouter, Depends, HTTPException
from models.subtrajectory import Subtrajectory
from services.subtrajectory_service import SubtrajectoryService
from services.similarity_service import SimilarityService
router = APIRouter(prefix="/api/subtrajectories")


@router.get("/get", response_model=list[Subtrajectory])
def get_subtrajectories(
    subtrajectory_service: Annotated[SubtrajectoryService, Depends(get_subtrajectory_service)],
    similirity_service: Annotated[SimilarityService, Depends(get_subtrajectory_service)],
    a_longitude: float,
    a_latitude: float,
    b_longitude: float,
    b_latitude: float,
    start_date: date,
    end_date: date,
    epsilon: float = 100,
    box_half_width_m: float = 50,
):
    """Return the subtrajectories from location A to location B in the date range given."""
    try:
        subtrajectory_list = subtrajectory_service.find_subtrajectories(
            a_longitude, a_latitude, b_longitude, b_latitude, start_date, end_date, box_half_width_m
        )
        pathlets = similirity_service.find_similar_trajectories(subtrajectory_list, epsilon)
        print(pathlets)
        return pathlets

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
