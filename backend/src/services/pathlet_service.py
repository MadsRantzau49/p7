"""Adapt frontend data to the pipeline without database access or debug output."""

from collections.abc import Iterable

from models.pathlet_api import (
    PathletClusteringRequest,
    PathletClusteringResponse,
    PreviewTrajectoryResponse,
)
from models.uniformed_trajectories import UniformedTrajectoryPoint
from pathlets.loading import parse_trajectories
from pathlets.main import run_pipeline
from pathlets.models import ClusteringConfig, GPSTrajectory


def cluster_loaded_trajectories(request: PathletClusteringRequest) -> PathletClusteringResponse:
    """Cluster exactly the loaded source trajectories, returning an in-memory result."""
    trajectories: list[GPSTrajectory] = []
    for source in request.trajectories:
        trajectory_id = str(source.trajectory_id)
        if not trajectory_id.strip():
            raise ValueError("trajectory IDs cannot be empty")
        if source.source_rows and (
            len(source.source_rows) != len(source.points) or any(row < 1 for row in source.source_rows)
        ):
            raise ValueError(f"source_rows must identify each original point in {trajectory_id!r}")
        try:
            ordered = all(
                a.point_timestamp < b.point_timestamp
                for a, b in zip(source.points, source.points[1:], strict=False)
            )
        except TypeError as error:
            raise ValueError(f"timestamps must use consistent time zones within {trajectory_id!r}") from error
        if not ordered:
            raise ValueError(f"timestamps must increase within {trajectory_id!r}")
        trajectories.append(
            GPSTrajectory(
                trajectory_id,
                tuple(
                    UniformedTrajectoryPoint(p.longitude, p.point_timestamp, p.latitude)
                    for p in source.points
                ),
                tuple(source.source_rows),
            )
        )
    result = run_pipeline(
        ClusteringConfig(
            epsilon_m=request.epsilon_m,
            use_spatial_index=request.use_spatial_index,
            use_bounding_box_filter=request.use_bounding_box_filter,
            output_dir=None,
        ),
        trajectories,
    )
    return PathletClusteringResponse(pathlets=result.pathlets, metrics=dict(result.metrics))


def preview_trajectory_csv(lines: Iterable[str]) -> list[PreviewTrajectoryResponse]:
    """Expose CSV points in the explorer's format, preserving IDs and source rows."""
    trajectories = parse_trajectories(lines)
    return [
        PreviewTrajectoryResponse(
            trajectory_id=t.trajectory_id,
            vehicle_id=int(t.metadata.get("vehicle_id") or 0),
            vehicle_type=str(t.metadata.get("vehicle_type") or "UNKNOWN"),
            trajectory_date=t.points[0].point_timestamp,
            city=str(t.metadata["city"]) if t.metadata.get("city") is not None else None,
            source_id=str(t.metadata["source_id"]) if t.metadata.get("source_id") is not None else None,
            points=list(t.points),
            source_rows=list(t.source_rows),
        )
        for t in trajectories
    ]
