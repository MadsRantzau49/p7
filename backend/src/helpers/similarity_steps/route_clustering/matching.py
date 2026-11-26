import math
from dataclasses import dataclass

from models.similarity import Polyline, ProjectedPoint

# A free interval is the sub-range [lo, hi] of a segment that lies within epsilon of a point,
# or None when no part of the segment is close enough.
Interval = tuple[float, float] | None


@dataclass
class MatchingCounts:
    """Count the workload of anchor comparisons without profiling the inner loop."""

    comparisons: int = 0
    endpoint_rejections: int = 0
    successful_matches: int = 0
    free_space_runs: int = 0
    free_space_cells: int = 0
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
    matches = _frechet_within(first.points, second.points, epsilon, counts)
    if counts is not None:
        counts.comparisons += 1
        counts.successful_matches += matches
    return matches


def _distance(first: ProjectedPoint, second: ProjectedPoint) -> float:
    """Euclidean distance between two projected points, in metres."""
    return math.hypot(first.x - second.x, first.y - second.y)


def _free_interval(
    point: ProjectedPoint, start: ProjectedPoint, end: ProjectedPoint, epsilon: float
) -> Interval:
    """Return the part [lo, hi] of segment start->end within epsilon of point, or None.

    Solving ||point - (start + h·(end - start))|| <= epsilon for h gives a quadratic; its roots,
    clamped to [0, 1], bound the free interval. A zero-length segment is in or out as a whole.
    """
    dx = end.x - start.x
    dy = end.y - start.y
    offset_x = start.x - point.x
    offset_y = start.y - point.y

    a = dx * dx + dy * dy
    b = 2 * (offset_x * dx + offset_y * dy)
    c = offset_x * offset_x + offset_y * offset_y - epsilon * epsilon

    if a == 0:
        return (0.0, 1.0) if c <= 0 else None

    discriminant = b * b - 4 * a * c
    if discriminant < 0:
        return None

    root = math.sqrt(discriminant)
    low = max(0.0, (-b - root) / (2 * a))
    high = min(1.0, (-b + root) / (2 * a))
    if low > high:
        return None
    return (low, high)


def _clip_from(interval: Interval, lowest: float) -> Interval:
    """Keep only the part of interval at or above lowest, preserving the upper bound."""
    if interval is None or interval[1] < lowest:
        return None
    return (max(interval[0], lowest), interval[1])


def _frechet_within(
    first: list[ProjectedPoint], second: list[ProjectedPoint], epsilon: float, counts: MatchingCounts | None
) -> bool:
    """Decide whether a monotone matching of first and second stays within epsilon throughout.

    This fills the Alt-Godau free-space diagram: each cell holds the part of a segment reachable
    by a forward-only path from the start. The routes match when such a path reaches the end.
    """
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

    # left[i][j]:   reachable range on the vertical line at first-vertex i, over second-segment j.
    # bottom[i][j]: reachable range on the horizontal line at second-vertex j, over first-segment i.
    left: list[list[Interval]] = [[None] * (m - 1) for _ in range(n)]
    bottom: list[list[Interval]] = [[None] * m for _ in range(n - 1)]

    for i in range(n):
        for j in range(m):
            if j < m - 1:
                left[i][j] = _reachable_left(first, second, left, bottom, i, j, epsilon)
            if i < n - 1:
                bottom[i][j] = _reachable_bottom(first, second, left, bottom, i, j, epsilon)

    top = left[n - 1][m - 2]
    right = bottom[n - 2][m - 1]
    reached_top = top is not None and top[1] == 1.0
    reached_right = right is not None and right[1] == 1.0
    return reached_top or reached_right


def _reachable_left(
    first: list[ProjectedPoint],
    second: list[ProjectedPoint],
    left: list[list[Interval]],
    bottom: list[list[Interval]],
    i: int,
    j: int,
    epsilon: float,
) -> Interval:
    """Reachable range on the vertical edge at first-vertex i over second-segment j."""
    free = _free_interval(first[i], second[j], second[j + 1], epsilon)
    if free is None:
        return None

    if i == 0:
        if j == 0:
            return free if free[0] == 0.0 else None
        # On the left wall, movement is only upward, so the column must be free without a gap.
        previous = left[0][j - 1]
        if previous is not None and previous[1] == 1.0 and free[0] == 0.0:
            return free
        return None

    # The edge is entered from the cell to the left, through its bottom or its left edge.
    if bottom[i - 1][j] is not None:
        return free
    left_below = left[i - 1][j]
    if left_below is not None:
        return _clip_from(free, left_below[0])
    return None


def _reachable_bottom(
    first: list[ProjectedPoint],
    second: list[ProjectedPoint],
    left: list[list[Interval]],
    bottom: list[list[Interval]],
    i: int,
    j: int,
    epsilon: float,
) -> Interval:
    """Reachable range on the horizontal edge at second-vertex j over first-segment i."""
    free = _free_interval(second[j], first[i], first[i + 1], epsilon)
    if free is None:
        return None

    if j == 0:
        if i == 0:
            return free if free[0] == 0.0 else None
        # On the bottom wall, movement is only rightward, so the row must be free without a gap.
        previous = bottom[i - 1][0]
        if previous is not None and previous[1] == 1.0 and free[0] == 0.0:
            return free
        return None

    # The edge is entered from the cell below, through its left or its bottom edge.
    if left[i][j - 1] is not None:
        return free
    bottom_prev = bottom[i][j - 1]
    if bottom_prev is not None:
        return _clip_from(free, bottom_prev[0])
    return None
