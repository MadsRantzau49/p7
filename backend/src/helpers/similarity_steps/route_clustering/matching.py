import math
from collections.abc import Iterator
from dataclasses import dataclass

from models.similarity import Polyline, ProjectedPoint

# A free interval is the sub-range [lo, hi] of a segment that lies within epsilon of a point,
# or None when no part of the segment is close enough.
Range = tuple[float, float]
Interval = Range | None


@dataclass
class MatchingCounts:
    """Count the workload of anchor comparisons without profiling the inner loop."""

    comparisons: int = 0
    endpoint_bucket_skips: int = 0
    bounds_rejections: int = 0
    endpoint_rejections: int = 0
    successful_matches: int = 0
    free_space_runs: int = 0
    free_space_cells: int = 0
    visited_free_space_cells: int = 0
    largest_free_space_cells: int = 0


def routes_match(
    first: Polyline, second: Polyline, epsilon: float, counts: MatchingCounts | None = None
) -> bool:
    """Return whether the continuous Fréchet distance between two routes is within epsilon.

    The Fréchet distance is the shortest leash that lets two walkers follow the routes from
    start to end without ever walking backwards. It keeps the order of travel and pins start to
    start and end to end, and it is the largest separation along the way, so a single stretch
    further than epsilon apart keeps the routes separate. Reversing a route, or ending somewhere
    else, therefore does not match.
    """
    matches = _frechet_within(first, second, epsilon, counts)
    if counts is not None:
        counts.comparisons += 1
        counts.successful_matches += matches
    return matches


def _distance(first: ProjectedPoint, second: ProjectedPoint) -> float:
    """Euclidean distance between two projected points, in metres."""
    return math.hypot(first.x - second.x, first.y - second.y)


def _free_interval(
    point: ProjectedPoint, start: ProjectedPoint, vector: tuple[float, float, float], epsilon_squared: float
) -> Interval:
    """Return the part [lo, hi] of segment start->end within epsilon of point, or None.

    Solving ||point - (start + h·(end - start))|| <= epsilon for h gives a quadratic; its roots,
    clamped to [0, 1], bound the free interval. A zero-length segment is in or out as a whole.
    """
    dx, dy, a = vector
    offset_x = start.x - point.x
    offset_y = start.y - point.y

    b = 2 * (offset_x * dx + offset_y * dy)
    c = offset_x * offset_x + offset_y * offset_y - epsilon_squared

    if a == 0:
        return (0.0, 1.0) if c <= 0 else None

    discriminant = b * b - 4 * a * c
    if discriminant < 0:
        return None

    root = math.sqrt(discriminant)
    denominator = 2 * a
    low = (-b - root) / denominator
    high = (-b + root) / denominator
    low = low if low > 0 else 0.0
    high = high if high < 1 else 1.0
    if low > high:
        return None
    return (low, high)


def _clip_from(interval: Interval, lowest: float) -> Interval:
    """Keep only the part of interval at or above lowest, preserving the upper bound."""
    if interval is None or interval[1] < lowest:
        return None
    return (max(interval[0], lowest), interval[1])


def _frechet_within(
    first_line: Polyline, second_line: Polyline, epsilon: float, counts: MatchingCounts | None
) -> bool:
    """Decide whether a monotone matching of first and second stays within epsilon throughout.

    Propagate reachable intervals through the Alt-Godau diagram. A cell with no reachable
    left or bottom edge cannot contribute to a match, so skip it without solving any quadratics.
    """
    first, second = first_line.points, second_line.points
    n = len(first)
    m = len(second)
    if n == 0 or m == 0:
        return False

    # The endpoints are pinned together, so they must already be within epsilon.
    if _distance(first[0], second[0]) > epsilon or _distance(first[-1], second[-1]) > epsilon:
        if counts is not None:
            counts.endpoint_rejections += 1
        return False

    # A single-point route only matches if every point of the other stays within epsilon.
    if n == 1:
        return all(_distance(first[0], point) <= epsilon for point in second)
    if m == 1:
        return all(_distance(point, second[0]) <= epsilon for point in first)

    if counts is not None:
        cells = (n - 1) * (m - 1)
        counts.free_space_runs += 1
        counts.free_space_cells += cells
        counts.largest_free_space_cells = max(counts.largest_free_space_cells, cells)

    matches, visited = _reachable_end(first_line, second_line, epsilon)
    if counts is not None:
        counts.visited_free_space_cells += visited
    return matches


def _boundary(fixed_point: ProjectedPoint, moving: Polyline, epsilon_squared: float) -> Iterator[Range]:
    """Yield the consecutive reachable ranges along a starting wall of the diagram."""
    for i, vector in enumerate(moving.segment_vectors):
        free = _free_interval(fixed_point, moving.points[i], vector, epsilon_squared)
        if free is None or free[0] != 0.0:
            break
        yield free
        if free[1] != 1.0:
            break


def _reachable_end(first_line: Polyline, second_line: Polyline, epsilon: float) -> tuple[bool, int]:
    """Sweep reachable cells, keeping only the current and next row of left edges."""
    first, second = first_line.points, second_line.points
    first_vectors, second_vectors = first_line.segment_vectors, second_line.segment_vectors
    epsilon_squared = epsilon * epsilon
    incoming = list(enumerate(_boundary(first[0], second_line, epsilon_squared)))
    bottom_wall = _boundary(second[0], first_line, epsilon_squared)
    last_i, last_j = len(first) - 2, len(second) - 2
    visited = 0
    for i, a_vector in enumerate(first_vectors):
        bottom = next(bottom_wall, None)
        if not incoming and bottom is None:
            break
        a_start, a_end = first[i], first[i + 1]
        outgoing: list[tuple[int, Range]] = []
        edges = iter(incoming)
        next_left = next(edges, None)
        j = 0
        while j <= last_j and (bottom is not None or next_left is not None):
            # Without an edge from below, jump directly to the next cell reachable from the left.
            left = None
            if next_left is not None and (bottom is None or j == next_left[0]):
                j, left = next_left
                next_left = next(edges, None)

            b_start, b_end = second[j], second[j + 1]
            # A path from the bottom can reach the whole free right edge. A path from the
            # left can only reach its forward portion. The top edge is the mirror case.
            right = _free_interval(a_end, b_start, second_vectors[j], epsilon_squared)
            top = _free_interval(b_end, a_start, a_vector, epsilon_squared)
            if bottom is None and left is not None:
                right = _clip_from(right, left[0])
            if left is None and bottom is not None:
                top = _clip_from(top, bottom[0])
            visited += 1

            if i == last_i and j == last_j:
                return any(edge is not None and edge[1] == 1.0 for edge in (right, top)), visited
            if right is not None:
                outgoing.append((j, right))
            bottom = top
            j += 1
        incoming = outgoing
    return False, visited
