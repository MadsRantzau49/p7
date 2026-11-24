from datetime import date, time
from typing import Annotated

from dependencies import get_route_clustering_service, get_subtrajectory_service
from fastapi import APIRouter, Depends, HTTPException
from models.similarity import (
    ClusterSubtrajectoriesRequest,
    ClusterSubtrajectory,
    GPSCoordinate,
    Route,
)
from services.clustering_service import ClusteringService
from services.subtrajectory_service import SubtrajectoryService

router = APIRouter(prefix="/api/subtrajectories")


@router.get("/get", response_model=list[Route])
def get_subtrajectories(
    subtrajectory_service: Annotated[SubtrajectoryService, Depends(get_subtrajectory_service)],
    route_clustering_service: Annotated[ClusteringService, Depends(get_route_clustering_service)],
    a_longitude: float,
    a_latitude: float,
    b_longitude: float,
    b_latitude: float,
    start_date: date,
    end_date: date,
    epsilon: float = 100,
    box_half_width_m: float = 50,
    start_time: time | None = None,
    end_time: time | None = None,
):
    """Return the clustered routes from location A to location B in the date range given.

    start_time and end_time optionally limit the local time of day the trip leaves A.
    If start_time is after end_time, the window wraps around midnight (e.g. 22:00 to 02:00).
    """
    try:
        subtrajectory_list = subtrajectory_service.find_subtrajectories(
            a_longitude,
            a_latitude,
            b_longitude,
            b_latitude,
            start_date,
            end_date,
            box_half_width_m,
            start_time,
            end_time,
        )
        routes = route_clustering_service.find_routes(subtrajectory_list, epsilon)
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
            request.a_longitude,
            request.a_latitude,
            request.b_longitude,
            request.b_latitude,
            request.start_date,
            request.end_date,
            request.box_half_width_m,
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
