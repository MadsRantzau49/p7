from datetime import time
from typing import Annotated

from dependencies import get_health_service, get_route_clustering_service, get_subtrajectory_service
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from models.bounding_box import BoundingBox
from models.date_range import DateRange
from models.similarity import (
    ClusterSubtrajectoriesRequest,
    ClusterSubtrajectory,
    GPSCoordinate,
    Route,
)
from services.clustering_service import ClusteringService
from services.health_service import HealthService
from services.subtrajectory_service import SubtrajectoryService

router = APIRouter(prefix="/api/subtrajectories")
Longitude = Annotated[float, Query(ge=-180, le=180, allow_inf_nan=False)]
Latitude = Annotated[float, Query(ge=-90, le=90, allow_inf_nan=False)]


@router.get("/get", response_model=list[Route])
def get_subtrajectories(
    subtrajectory_service: Annotated[SubtrajectoryService, Depends(get_subtrajectory_service)],
    route_clustering_service: Annotated[ClusteringService, Depends(get_route_clustering_service)],
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
    """Return the clustered routes between two non-overlapping bounding boxes in the date range.

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

        routes = route_clustering_service.find_routes(subtrajectory_list, epsilon)

        if not routes:
            raise HTTPException(status_code=404, detail="No routes found for the given parameters.")

        return routes

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/cluster", response_model=list[ClusterSubtrajectory])
def get_cluster_subtrajectories(
    request: ClusterSubtrajectoriesRequest,
    subtrajectory_service: Annotated[SubtrajectoryService, Depends(get_subtrajectory_service)],
):
    """Return the subtrajectories of one cluster, fetched on demand when the cluster is opened.

    The request carries the same query that produced the routes plus the cluster's members, so
    the subtrajectories are re-extracted and filtered to those members without keeping any state
    between requests.
    """
    try:
        subtrajectories = subtrajectory_service.find_subtrajectories(
            BoundingBox(
                request.a_longitude,
                request.a_latitude,
                request.a_max_longitude,
                request.a_max_latitude,
            ),
            BoundingBox(
                request.b_longitude,
                request.b_latitude,
                request.b_max_longitude,
                request.b_max_latitude,
            ),
            DateRange(request.start_date, request.end_date),
            request.start_time,
            request.end_time,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    wanted = {(member.trajectory_id, member.exit_a_time, member.entry_b_time) for member in request.members}

    return [
        ClusterSubtrajectory(
            trajectory_id=subtrajectory.trajectory_id,
            points=[
                GPSCoordinate(latitude=point.latitude, longitude=point.longitude)
                for point in subtrajectory.points
            ],
        )
        for subtrajectory in subtrajectories
        if (subtrajectory.trajectory_id, subtrajectory.exit_a_time, subtrajectory.entry_b_time) in wanted
    ]


@router.get("/health", response_model=dict[str, str])
def check_health(response: Response, health_service: Annotated[HealthService, Depends(get_health_service)]):
    """A simple endpoint to check if the service is running."""
    result = health_service.check_health()
    if result["status"] != "healthy":
        response.status_code = 503
    return result
