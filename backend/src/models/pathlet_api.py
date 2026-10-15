"""Validated transport models, separate from the geometric stage contracts."""

from datetime import datetime
from typing import Literal

from pathlets.models import GPSPathlet
from pydantic import BaseModel, Field

from models.uniformed_trajectories import UniformedTrajectoryPoint


class PathletPointRequest(BaseModel):
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    point_timestamp: datetime


class PathletTrajectoryRequest(BaseModel):
    trajectory_id: int | str
    points: list[PathletPointRequest] = Field(min_length=2)
    source_rows: list[int] = Field(default_factory=list)


class PathletClusteringRequest(BaseModel):
    trajectories: list[PathletTrajectoryRequest] = Field(min_length=1)
    epsilon_m: float = Field(default=100.0, ge=0, allow_inf_nan=False)


class PathletClusteringResponse(BaseModel):
    coordinate_order: Literal["latitude,longitude"] = "latitude,longitude"
    pathlets: list[GPSPathlet]
    metrics: dict[str, object]


class PreviewTrajectoryResponse(BaseModel):
    trajectory_id: str
    vehicle_id: int
    vehicle_type: str
    trajectory_date: datetime
    city: str | None
    source_id: str | None
    points: list[UniformedTrajectoryPoint]
    source_rows: list[int]
