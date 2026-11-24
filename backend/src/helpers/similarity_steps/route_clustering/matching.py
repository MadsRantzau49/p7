import math

from helpers.similarity_steps.route_clustering.geometry import (
    point_at_fraction,
    project_onto_segment,
    squared_distance,
)
from models.similarity import Polyline, ProjectedPoint


def routes_match(first: Polyline, second: Polyline, epsilon: float) -> bool:
    """Return whether two routes stay within epsilon metres of each other end to end.

    The check is symmetric and keeps order: every point of each route must lie within
    epsilon of the other route while moving forward along it. The per-point maximum is used,
    so a single stretch further than epsilon apart keeps the routes separate. A shared opening
    that later diverges therefore does not count as the same route.
    """
    return _covers(first, second, epsilon) and _covers(second, first, epsilon)


def _covers(source: Polyline, target: Polyline, epsilon: float) -> bool:
    """Return whether every point of source lies within epsilon of target, moving forward."""
    epsilon_squared = epsilon * epsilon
    cursor = 0.0
    for point in source.points:
        cursor, distance_squared = _nearest_forward(target, point, cursor)
        if distance_squared > epsilon_squared:
            return False
    return True


def _nearest_forward(target: Polyline, point: ProjectedPoint, cursor: float) -> tuple[float, float]:
    """Return the closest position on target at or beyond cursor metres.

    The result is the position's arc length from target's start and its squared distance from
    point. The cursor never moves backward, which keeps the correspondence ordered.
    """
    best_distance = cursor
    best_squared = math.inf
    for index in range(target.segment_count):
        segment_start = target.cumulative_lengths[index]
        segment_end = target.cumulative_lengths[index + 1]
        if segment_end < cursor:
            continue

        start = target.points[index]
        end = target.points[index + 1]
        dx = end.x - start.x
        dy = end.y - start.y
        length_squared = dx * dx + dy * dy
        fraction = project_onto_segment(point, start, dx, dy, length_squared)

        # Do not step back before the cursor inside a segment that straddles it.
        along = segment_start + fraction * (segment_end - segment_start)
        if along < cursor:
            along = cursor
            span = segment_end - segment_start
            fraction = (cursor - segment_start) / span if span > 0 else 0.0

        projected_x, projected_y = point_at_fraction(start, end, dx, dy, fraction)
        distance_squared = squared_distance(point.x, point.y, projected_x, projected_y)

        if distance_squared < best_squared:
            best_squared = distance_squared
            best_distance = along

    return best_distance, best_squared
