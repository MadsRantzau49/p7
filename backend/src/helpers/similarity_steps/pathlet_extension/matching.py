import math
from operator import itemgetter

from helpers.similarity_steps.pathlet_extension.geometry import (
    distance_along,
    dot,
    interpolate,
    point_at_fraction,
    project_onto_segment,
    squared_distance,
)
from helpers.similarity_steps.pathlet_extension.representative_grid import (
    RepresentativeGrid,
)
from models.similarity import Match, Polyline, ProjectedPoint, Seed

FORWARD = 1
BACKWARD = -1
# Angles between 45 and 135 degrees count as crossings.
CROSSING_COS_SQUARED = 0.5

def find_match(trajectory: Polyline, start: int, grid: RepresentativeGrid) -> Match | None:
    """Return the first accepted match starting at trajectory point start.

    Try ranked seeds in their preferred direction, then the opposite direction.
    Return None if no attempt accepts at least one whole source segment.
    """
    seeds = grid.seeds_near(trajectory.points[start])
    if not seeds:
        return None

    for seed, preferred in _rank_seeds(seeds, trajectory, start, grid.epsilon):
        for direction in (preferred, -preferred):
            match = _advance(trajectory, start, seed, direction, grid.epsilon)
            if match is not None:
                return match
    return None


def _rank_seeds(
    seeds: list[Seed], trajectory: Polyline, start: int,epsilon : float
) -> list[tuple[Seed, int]]:
    """Rank seeds by length suitability, available room, crossing, and proximity.

    Prefer representatives at least epsilon long, room for half the source
    segment, and non-crossing alignment. Return (seed, preferred_direction) pairs.
    """
    a, b = trajectory.points[start], trajectory.points[start + 1]
    dx, dy = b.x - a.x, b.y - a.y
    trajectory_squared = dx * dx + dy * dy
    half_segment_length = trajectory.segment_lengths[start] / 2

    ranked = []

    for seed in seeds:
        segment = seed.segment
        line = seed.representative.polyline

        alignment = dot(segment.dx, segment.dy, dx, dy)
        direction = FORWARD if alignment >= 0 else BACKWARD

        position = distance_along(line, seed.segment_index, seed.fraction)
        available = (
            line.total_length - position
            if direction == FORWARD
            else position
        )

        is_crossing = alignment * alignment < (
            CROSSING_COS_SQUARED * trajectory_squared * segment.length_squared
        )

        priority = (
            line.total_length < epsilon,
            available < half_segment_length,
            is_crossing,
            seed.distance_squared,
        )
        ranked.append((priority, seed, direction))

    ranked.sort(key=itemgetter(0))
    return [(seed, direction) for _, seed, direction in ranked]

def _advance(
    trajectory: Polyline, start: int, seed: Seed, direction: int, epsilon: float,
) -> Match | None:
    """Greedily match trajectory segments onto the seed's representative.

        Starting at trajectory point ``start`` and the seed's position on the
        representative, walk the trajectory one segment at a time while moving
        along the representative in ``direction`` only. A segment is accepted when
        its end point lies within ``epsilon`` of the representative ahead of the
        current position, and every representative corner passed on the way lies
        within ``epsilon`` of the segment under a steady-pace pairing. The walk
        stops at the first segment that fails, so the match is one contiguous run
        starting at ``start``.

        Returns None if not even the first segment can be matched.
        """
    rep_line = seed.representative.polyline
    points = rep_line.points
    cumulative_distances = rep_line.cumulative_lengths
    epsilon_squared = epsilon * epsilon

    current_segment = seed.segment_index
    current_fraction = seed.fraction
    current_distance = distance_along(rep_line, current_segment, current_fraction)
    start_distance = current_distance
    end = start

    for trajectory_segment in range(start, trajectory.segment_count):
        trajectory_start = trajectory.points[trajectory_segment]
        trajectory_end = trajectory.points[trajectory_segment + 1]
        reach = trajectory.segment_lengths[trajectory_segment] + 2 * epsilon

        best_distance_squared = math.inf
        next_segment = current_segment
        next_fraction = current_fraction
        candidate_segment = current_segment

        # Search for the closest position on the representative
        while 0 <= candidate_segment < rep_line.segment_count:
            rep_start = points[candidate_segment]
            rep_end = points[candidate_segment + 1]
            dx = rep_end.x - rep_start.x
            dy = rep_end.y - rep_start.y
            length_squared = dx * dx + dy * dy
            fraction = project_onto_segment(trajectory_end, rep_start, dx, dy, length_squared)
            if candidate_segment == current_segment:
                if (direction == FORWARD and fraction < current_fraction) or (
                    direction == BACKWARD and fraction > current_fraction):
                    fraction = current_fraction

            projected_x, projected_y = point_at_fraction(rep_start, rep_end, dx, dy, fraction)
            distance_squared = squared_distance(trajectory_end.x, trajectory_end.y, projected_x, projected_y)

            if distance_squared < best_distance_squared:
                best_distance_squared = distance_squared
                next_segment, next_fraction = candidate_segment, fraction
            elif length_squared and best_distance_squared <= epsilon_squared:
                break

            candidate_segment += direction
            boundary = candidate_segment if direction == FORWARD else candidate_segment + 1
            if 0 <= boundary < len(cumulative_distances):
                if abs(cumulative_distances[boundary] - current_distance) > reach:
                    break

        if best_distance_squared > epsilon_squared:
            break

        # Check every traversed corner using a steady-pace pairing.
        # Together with the endpoints, these checks cover the entire segment.
        next_distance = distance_along(rep_line, next_segment, next_fraction)
        if direction == FORWARD:
            corners = range(current_segment + 1, next_segment + 1)
        else:
            corners = range(current_segment, next_segment, -1)

        if not _corners_within_epsilon(
            rep_line, corners, current_distance, next_distance,
            trajectory_start, trajectory_end, epsilon_squared,
        ):
            break
        # Commit only after the endpoint and every traversed corner pass.
        current_segment, current_fraction, current_distance = next_segment, next_fraction, next_distance
        end = trajectory_segment + 1

    if end == start:
        return None
    return Match(
        representative=seed.representative,
        end_index=end,
        start_m=start_distance,
        end_m=current_distance,
    )

def _corners_within_epsilon(
    rep_line: Polyline,
    corners: range,
    from_distance: float,
    to_distance: float,
    segment_start: ProjectedPoint,
    segment_end: ProjectedPoint,
    epsilon_squared: float,
) -> bool:
    """Walk the trajectory segment at a steady pace from from_distance to
    to_distance along rep_line, and check it passes within epsilon of
    every corner in corners."""
    advance = abs(to_distance - from_distance)
    for corner in corners:
        along = abs(rep_line.cumulative_lengths[corner] - from_distance) / advance if advance else 0.0
        x, y = interpolate(segment_start, segment_end, along)
        point = rep_line.points[corner]
        if squared_distance(x, y, point.x, point.y) > epsilon_squared:
            return False
    return True
