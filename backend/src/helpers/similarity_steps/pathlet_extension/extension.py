from operator import attrgetter
from statistics import median

from helpers.similarity_steps.pathlet_extension.matching import find_match
from helpers.similarity_steps.pathlet_extension.representative_grid import RepresentativeGrid
from helpers.similarity_steps.pathlet_extension.support import support_intervals
from models.similarity import (
    Polyline,
    ProjectedPathlet,
    ProjectedTrajectory,
    Representative,
    TrajectoryLine,
    TrajectorySection,
)


def extend_pathlets(trajectories: list[ProjectedTrajectory], epsilon: float) -> list[ProjectedPathlet]:
    """Build pathlets using an epsilon distance bound in metres.

    Process longer trajectories first and assign every source segment once.
    Return representative points with overall and local support counts.
    """
    lines = []
    for _, trajectory in enumerate(trajectories):
        polyline = Polyline.from_points(trajectory.projected_points)
        lines.append(TrajectoryLine(trajectory.trajectory_id, polyline))

    lengths = []
    for line in lines:
        for length in line.polyline.segment_lengths:
            if length > 0:
                lengths.append(length)

    if lengths:
        cell_size = max(epsilon, median(lengths), 1.0)
    else:
        cell_size = max(epsilon, 1.0)

    grid = RepresentativeGrid(epsilon, cell_size)
    representatives: list[Representative] = []

    sorted_trajectories = sorted(lines, key=attrgetter("polyline.total_length"), reverse=True)
    for trajectory in sorted_trajectories:
        assign_trajectory(trajectory, grid, representatives)

    projected_pathlets = []
    for representative in representatives:
        projected_pathlets.append(to_projected_pathlet(representative))
    return projected_pathlets


def assign_trajectory(
    line: TrajectoryLine,
    grid: RepresentativeGrid,
    representatives: list[Representative],
) -> None:
    """Walk one trajectory and assign each stretch: to a representative, or as a new one.

    New representatives are appended to `representatives` and added to `grid`.
    """
    polyline = line.polyline
    start = 0
    pending = None  # a match already found while scanning ahead
    while start < polyline.segment_count:
        if pending is not None:
            match = pending
        else:
            match = find_match(polyline, start, grid)
        pending = None

        # Match found: assign the stretch to that representative.
        if match is not None:
            section = TrajectorySection(
                trajectory_id=line.trajectory_id,
                representative_start_m=min(match.start_m, match.end_m),
                representative_end_m=max(match.start_m, match.end_m),
            )

            match.representative.assigned_sections.append(section)
            start = match.end_index
            continue

        # No match: scan ahead to the first point where a match begins (or the last point).
        end = start + 1
        while end < polyline.segment_count:
            pending = find_match(polyline, end, grid)
            if pending is not None:
                break
            end += 1

        # Everything from start to end becomes a new representative.
        representative_line = Polyline.from_points(polyline.points[start : end + 1])
        own_section = TrajectorySection(
            trajectory_id=line.trajectory_id,
            representative_start_m=0.0,
            representative_end_m=representative_line.total_length,
        )
        representative = Representative(representative_line, own_section)
        representatives.append(representative)
        grid.add(representative)
        start = end


def to_projected_pathlet(representative: Representative) -> ProjectedPathlet:
    """Return representative points with trajectory counts and support intervals.

    Count distinct source IDs with positive-length coverage. For a zero-length
    representative, count all assigned source IDs. Support distances use metres.
    """
    sections = [representative.own_section]
    sections.extend(representative.assigned_sections)

    total_length_m = representative.polyline.total_length
    if total_length_m == 0:
        # Degenerate representative: every section has zero length, so count them all.
        covering = sections
    else:
        covering = []
        for section in sections:
            if section.representative_end_m > section.representative_start_m:
                covering.append(section)

    trajectory_ids = set()
    for section in covering:
        trajectory_ids.add(section.trajectory_id)

    return ProjectedPathlet(
        points=representative.polyline.points,
        count=len(trajectory_ids),
        support=support_intervals(sections, total_length_m),
    )
