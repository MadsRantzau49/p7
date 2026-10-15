"""Frontend-facing in-memory pathlet clustering and CSV preview endpoints."""

import io
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile
from models.pathlet_api import (
    PathletClusteringRequest,
    PathletClusteringResponse,
    PreviewTrajectoryResponse,
)
from services.pathlet_service import cluster_loaded_trajectories, preview_trajectory_csv

router = APIRouter(prefix="/api/trajectories", tags=["pathlets"])
MAX_PREVIEW_BYTES = 50 * 1024 * 1024


@router.post("/pathlets", response_model=PathletClusteringResponse)
def cluster_pathlets_endpoint(request: PathletClusteringRequest) -> PathletClusteringResponse:
    """Run CPU-bound geometry in FastAPI's worker thread, returning Leaflet coordinates."""
    try:
        return cluster_loaded_trajectories(request)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/preview", response_model=list[PreviewTrajectoryResponse])
def preview_trajectories_endpoint(file: Annotated[UploadFile, File()]) -> list[PreviewTrajectoryResponse]:
    """Preview an ordered CSV in the map without persisting it to the database."""
    if file.size is not None and file.size > MAX_PREVIEW_BYTES:
        raise HTTPException(status_code=413, detail="file is larger than 50 MB")
    lines = io.TextIOWrapper(file.file, encoding="utf-8-sig", newline="")
    try:
        return preview_trajectory_csv(lines)
    except UnicodeDecodeError as error:
        raise HTTPException(status_code=422, detail="file must be UTF-8 encoded") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    finally:
        lines.detach()  # UploadFile owns and closes the underlying stream.
