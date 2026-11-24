from datetime import time
from typing import Annotated

from dependencies import get_similarity_service, get_subtrajectory_service
from fastapi import APIRouter, Depends, HTTPException, Query
from models.bounding_box import BoundingBox
from models.date_range import DateRange
from models.similarity import Pathlet
from services.similarity_service import SimilarityService
from services.subtrajectory_service import SubtrajectoryService

router = APIRouter(prefix="/api/subtrajectories")
Longitude = Annotated[float, Query(ge=-180, le=180, allow_inf_nan=False)]
Latitude = Annotated[float, Query(ge=-90, le=90, allow_inf_nan=False)]


@router.get("/get", response_model=list[Pathlet])
def get_subtrajectories(
    subtrajectory_service: Annotated[SubtrajectoryService, Depends(get_subtrajectory_service)],
    similarity_service: Annotated[SimilarityService, Depends(get_similarity_service)],
    dates: Annotated[DateRange, Depends()],
    a_longitude: Longitude,
    a_latitude: Latitude,
    a_max_longitude: Longitude,
    a_max_latitude: Latitude,
    b_longitude: Longitude,
    b_latitude: Latitude,
    b_max_longitude: Longitude,
    b_max_latitude: Latitude,
    epsilon: float = 100,
    start_time: time | None = None,
    end_time: time | None = None,
):
    """Return pathlets between two non-overlapping bounding boxes in the date range given.

    A and B are minimum corners; a_max and b_max are maximum corners.
    start_time and end_time optionally limit the local time of day the trip leaves A.
    If start_time is after end_time, the window wraps around midnight (e.g. 22:00 to 02:00).
    """
    try:
        subtrajectory_list = subtrajectory_service.find_subtrajectories(
            BoundingBox(a_longitude, a_latitude, a_max_longitude, a_max_latitude),
            BoundingBox(b_longitude, b_latitude, b_max_longitude, b_max_latitude),
            dates,
            start_time,
            end_time,
        )
        pathlets = similarity_service.find_similar_trajectories(subtrajectory_list, epsilon)
        return pathlets

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
