"""File loading is independent of metric geometry and database services."""

from collections.abc import Iterable
from pathlib import Path

from helpers.upload_parser import parse_upload
from models.uniformed_trajectories import UniformedTrajectories, UniformedTrajectoryPoint

from .models import GPSTrajectory


def from_uniformed(trajectory_id: str, trajectory: UniformedTrajectories) -> GPSTrajectory:
    """Adapt an existing backend trajectory with an explicit stable source ID."""
    return GPSTrajectory(
        trajectory_id,
        tuple(trajectory.points),
        metadata={
            "vehicle_id": trajectory.vehicle_id,
            "database_trajectory_id": trajectory.trajectory_id,
            "source_id": trajectory.source_id,
            "city": trajectory.city,
        },
    )


def load_trajectories(path: Path) -> list[GPSTrajectory]:
    """Reuse row validation, preserving CSV IDs, point order, and row provenance."""
    with path.open(encoding="utf-8-sig", newline="") as source:
        return parse_trajectories(source)


def parse_trajectories(lines: Iterable[str]) -> list[GPSTrajectory]:
    """Parse an ordered CSV stream without requiring a file or database."""
    groups, errors = parse_upload(lines)
    if errors:
        raise ValueError("; ".join(f"line {error.line}: {error.message}" for error in errors[:10]))
    if not groups:
        raise ValueError("CSV contains no trajectories")
    result: list[GPSTrajectory] = []
    for trajectory_id, rows in sorted(groups.items()):
        if len(rows) < 2:
            raise ValueError(f"trajectory {trajectory_id!r} needs at least two points")
        first = rows[0][1]
        for (_, previous), (line, row) in zip(rows, rows[1:], strict=False):
            if row.timestamp <= previous.timestamp:
                raise ValueError(f"line {line}: timestamps must increase within {trajectory_id!r}")
            if (row.vehicle_id, row.vehicle_type, row.city, row.source_id, row.database_trajectory_id) != (
                first.vehicle_id,
                first.vehicle_type,
                first.city,
                first.source_id,
                first.database_trajectory_id,
            ):
                raise ValueError(f"line {line}: inconsistent metadata within {trajectory_id!r}")
        result.append(
            GPSTrajectory(
                trajectory_id,
                tuple(
                    UniformedTrajectoryPoint(row.longitude, row.timestamp, row.latitude) for _, row in rows
                ),
                tuple(line for line, _ in rows),
                {
                    "vehicle_id": first.vehicle_id,
                    "vehicle_type": first.vehicle_type.value,
                    "city": first.city,
                    "source_id": first.source_id,
                    "database_trajectory_id": first.database_trajectory_id,
                },
            )
        )
    return result
