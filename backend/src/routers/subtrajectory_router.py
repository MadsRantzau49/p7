from dataclasses import dataclass
from datetime import date, time
from typing import Annotated

import psycopg
from dependencies import get_similarity_service, get_subtrajectory_service
from fastapi import APIRouter, Depends, HTTPException, Query
from models.bounding_box import BoundingBox
from models.similarity import Pathlet
from models.subtrajectory import Subtrajectory
from services.similarity_service import SimilarityService
from services.subtrajectory_service import SubtrajectoryService

router = APIRouter(prefix="/api/subtrajectories")
Longitude = Annotated[float, Query(ge=-180, le=180)]
Latitude = Annotated[float, Query(ge=-90, le=90)]


@dataclass
class RouteSearchResult:
    """Clustered pathlets and their complete source A-to-B journeys."""

    pathlets: list[Pathlet]
    trajectories: list[Subtrajectory]


@router.get("/get", response_model=RouteSearchResult)
def get_subtrajectories(
    subtrajectory_service: Annotated[SubtrajectoryService, Depends(get_subtrajectory_service)],
    similarity_service: Annotated[SimilarityService, Depends(get_similarity_service)],
    a_longitude: Longitude,
    a_latitude: Latitude,
    a_max_longitude: Longitude,
    a_max_latitude: Latitude,
    b_longitude: Longitude,
    b_latitude: Latitude,
    b_max_longitude: Longitude,
    b_max_latitude: Latitude,
    start_date: date | None = None,
    end_date: date | None = None,
    epsilon: Annotated[float, Query(gt=0, allow_inf_nan=False)] = 100,
    start_time: time | None = None,
    end_time: time | None = None,
):
    """Return pathlets between two required, non-overlapping rectangles.

    start_time and end_time optionally limit the local time of day the trip leaves A.
    If start_time is after end_time, the window wraps around midnight (e.g. 22:00 to 02:00).
    A and B are minimum corners; a_max and b_max are maximum corners.
    Omitted dates impose no date limit.
    Each complete A-to-B source geometry is returned once alongside the pathlets.
    """
    try:
        subtrajectory_list = subtrajectory_service.find_subtrajectories(
            BoundingBox(a_longitude, a_latitude, a_max_longitude, a_max_latitude),
            BoundingBox(b_longitude, b_latitude, b_max_longitude, b_max_latitude),
            start_date,
            end_date,
            start_time,
            end_time,
        )
        pathlets = similarity_service.find_similar_trajectories(subtrajectory_list, epsilon) or []
        return RouteSearchResult(pathlets, subtrajectory_list)

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except psycopg.errors.QueryCanceled as error:
        raise HTTPException(status_code=504, detail="The search took too long. Try smaller areas.") from error
    except psycopg.OperationalError as error:
        raise HTTPException(
            status_code=503, detail="Lost the connection to the database. Please try again."
        ) from error
