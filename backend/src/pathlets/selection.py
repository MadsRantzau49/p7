"""Deterministic disjoint interval coverage and inverse projection."""

from bisect import bisect_left
from datetime import datetime
from math import ceil, floor

from pyproj import Transformer

from .extension import POSITION_TOLERANCE
from .geometry import interval_coordinates, length
from .models import (
    Assignment,
    ClusteringConfig,
    ExtendedPathletCandidate,
    GPSAssignment,
    GPSPathlet,
    MetricPathlet,
    MetricTrajectory,
    Projection,
)


def uncovered_intervals(end: float, covered: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Return the complement of an interval union in original point-index space."""
    cursor = 0.0
    result: list[tuple[float, float]] = []
    for start, stop in sorted(covered):
        if start > cursor:
            result.append((cursor, start))
        cursor = max(cursor, stop)
    if cursor < end:
        result.append((cursor, end))
    return result


def select_final_pathlets(
    candidates: list[ExtendedPathletCandidate],
    trajectories: list[MetricTrajectory],
    config: ClusteringConfig,
) -> list[MetricPathlet]:
    """Greedily maximize newly covered meters, then restore every uncovered part.

    Shared candidates must be wholly uncovered in *every* assigned original
    interval. This avoids ambiguous partial assignments or duplicate counts.
    Score is the sum of source lengths, with support and source position as
    deterministic tie breakers. Rejected partial overlaps become singletons
    unless another disjoint candidate covers them. No global optimum is claimed.
    """
    by_id = {trajectory.trajectory_id: trajectory for trajectory in trajectories}
    coverage: dict[str, list[tuple[float, float]]] = {trajectory_id: [] for trajectory_id in by_id}

    def score(candidate: ExtendedPathletCandidate) -> tuple[float, int, Assignment, tuple[Assignment, ...]]:
        meters = sum(length(interval_coordinates(by_id[a.trajectory_id], a)) for a in candidate.assignments)
        return -meters, -len(candidate.assignments), candidate.representative, candidate.assignments

    selected: list[tuple[Assignment, tuple[Assignment, ...], float]] = []
    for candidate in sorted(candidates, key=score):
        if (
            length(
                interval_coordinates(by_id[candidate.representative.trajectory_id], candidate.representative)
            )
            < config.min_pathlet_length_m
        ):
            continue
        overlapping = False
        for assignment in candidate.assignments:
            intervals = coverage[assignment.trajectory_id]
            index = bisect_left(intervals, (assignment.start,))
            if (index > 0 and intervals[index - 1][1] > assignment.start) or (
                index < len(intervals) and intervals[index][0] < assignment.end
            ):
                overlapping = True
                break
        if overlapping:
            continue
        selected.append((candidate.representative, candidate.assignments, candidate.max_sspd_m))
        for assignment in candidate.assignments:
            intervals = coverage[assignment.trajectory_id]
            intervals.insert(
                bisect_left(intervals, (assignment.start, assignment.end)), (assignment.start, assignment.end)
            )

    # No length threshold here: even a stationary original interval is preserved.
    for trajectory in trajectories:
        for start, end in uncovered_intervals(
            len(trajectory.coordinates) - 1, coverage[trajectory.trajectory_id]
        ):
            assignment = Assignment(trajectory.trajectory_id, start, end)
            selected.append((assignment, (assignment,), 0.0))
    selected.sort(key=lambda item: (item[0], item[1]))
    return [
        MetricPathlet(
            f"pathlet-{index:06d}",
            representative,
            interval_coordinates(by_id[representative.trajectory_id], representative),
            assignments,
            maximum,
        )
        for index, (representative, assignments, maximum) in enumerate(selected)
    ]


def validate_coverage(pathlets: list[MetricPathlet], trajectories: list[MetricTrajectory]) -> None:
    """Assert complete non-overlapping source coverage, including zero-length edges."""
    coverage: dict[str, list[tuple[float, float]]] = {t.trajectory_id: [] for t in trajectories}
    for pathlet in pathlets:
        ids = [assignment.trajectory_id for assignment in pathlet.assignments]
        if len(set(ids)) != len(ids):
            raise ValueError("a pathlet cannot count a trajectory more than once")
        for assignment in pathlet.assignments:
            if assignment.end <= assignment.start:
                raise ValueError("assignment must progress forward")
            coverage[assignment.trajectory_id].append((assignment.start, assignment.end))
    for trajectory in trajectories:
        cursor = 0.0
        for start, end in sorted(coverage[trajectory.trajectory_id]):
            if abs(start - cursor) > POSITION_TOLERANCE:
                raise ValueError(f"coverage gap or overlap in {trajectory.trajectory_id}")
            cursor = end
        if abs(cursor - (len(trajectory.coordinates) - 1)) > POSITION_TOLERANCE:
            raise ValueError(f"incomplete coverage of {trajectory.trajectory_id}")


def convert_to_gps(
    pathlets: list[MetricPathlet],
    trajectories: list[MetricTrajectory],
    projection: Projection,
) -> list[GPSPathlet]:
    """Inverse-project representatives into Leaflet latitude/longitude order."""
    transformer = Transformer.from_crs(projection.crs, "EPSG:4326", always_xy=True)
    by_id = {trajectory.trajectory_id: trajectory for trajectory in trajectories}

    def assignment_output(assignment: Assignment) -> GPSAssignment:
        trajectory = by_id[assignment.trajectory_id]

        def timestamp(position: float) -> datetime | None:
            index = min(floor(position), len(trajectory.coordinates) - 2)
            start, end = trajectory.timestamps[index : index + 2]
            if start is None or end is None:
                return None
            return start + (end - start) * (position - index)

        return GPSAssignment(
            assignment.trajectory_id,
            assignment.start,
            assignment.end,
            timestamp(assignment.start),
            timestamp(assignment.end),
            trajectory.source_rows[floor(assignment.start) : ceil(assignment.end) + 1],
        )

    result: list[GPSPathlet] = []
    for pathlet in pathlets:
        ids = tuple(sorted({assignment.trajectory_id for assignment in pathlet.assignments}))
        coordinates = tuple(
            (lat, lon) for lon, lat in (transformer.transform(x, y) for x, y in pathlet.coordinates)
        )
        result.append(
            GPSPathlet(
                pathlet.pathlet_id,
                coordinates,
                len(ids),
                ids,
                pathlet.representative,
                tuple(assignment_output(a) for a in pathlet.assignments),
                pathlet.max_sspd_m,
            )
        )
    return result
