import math
from itertools import pairwise

from models.similarity import Polyline, ProjectedPoint


def dot(ax: float, ay: float, bx: float, by: float) -> float:
    """Dot product of the vectors (ax, ay) and (bx, by).

    Positive: roughly the same direction. Zero: perpendicular. Negative: roughly opposite.
    """
    return ax * bx + ay * by


def squared_distance(ax: float, ay: float, bx: float, by: float) -> float:
    """Return the squared Euclidean distance between two points."""
    distance_x = ax - bx
    distance_y = ay - by
    return distance_x * distance_x + distance_y * distance_y


def project_onto_segment(
    point: ProjectedPoint,
    start: ProjectedPoint,
    dx: float,
    dy: float,
    length_squared: float,
) -> float:
    """Fraction t in [0, 1] of the spot on a segment closest to the point (x, y).

    The segment runs from `start` to `start + (dx, dy)`, and `length_squared` is dx² + dy².
    The unclamped t is the point's "shadow" on the segment's line; clamping keeps it on the
    segment itself. A zero-length segment (duplicate GPS point) always gives t = 0.
    """
    if length_squared:
        fraction = dot(point.x - start.x, point.y - start.y, dx, dy) / length_squared
    else:
        fraction = 0.0
    if fraction < 0:
        return 0.0
    if fraction > 1:
        return 1.0
    return fraction


def point_at_fraction(
    start: ProjectedPoint,
    end: ProjectedPoint,
    dx: float,
    dy: float,
    fraction: float,
) -> tuple[float, float]:
    """The point a fraction of the way along a segment: start + fraction · (dx, dy).

    At fraction 0 and 1 the original endpoints are returned exactly, so rounding can never
    make an endpoint look slightly further away (important when epsilon is 0).
    """
    if fraction <= 0:
        return start.x, start.y
    if fraction >= 1:
        return end.x, end.y
    return start.x + fraction * dx, start.y + fraction * dy


def interpolate(start: ProjectedPoint, end: ProjectedPoint, fraction: float) -> tuple[float, float]:
    """The point a fraction of the way from `start` to `end` (linear interpolation)."""
    return point_at_fraction(start, end, end.x - start.x, end.y - start.y, fraction)


def distance_along(
    polyline: Polyline,
    segment_index: int,
    fraction: float,
) -> float:
    """Metres from the polyline's start to a position on a segment."""
    return polyline.cumulative_lengths[segment_index] + fraction * polyline.segment_lengths[segment_index]


def cell_index(value: float, cell_size: float) -> int:
    """Index of the grid column or row that a coordinate falls in, for cells of side cell_size."""
    return math.floor(value / cell_size)


def polyline_cells(polyline: Polyline, cell_size: float) -> set[tuple[int, int]]:
    """Return the set of square grid cells of side cell_size that the polyline passes through.

    Each segment is sampled finely enough that no crossed cell is skipped, so two routes on the
    same roads share most of their cells. The set is used to pick a cluster's representative.
    """
    cells: set[tuple[int, int]] = set()
    points = polyline.points
    if not points:
        return cells

    cells.add((cell_index(points[0].x, cell_size), cell_index(points[0].y, cell_size)))
    for start, end in pairwise(points):
        length = math.hypot(end.x - start.x, end.y - start.y)
        steps = max(1, math.ceil(length / cell_size))
        for step in range(1, steps + 1):
            fraction = step / steps
            x = start.x + fraction * (end.x - start.x)
            y = start.y + fraction * (end.y - start.y)
            cells.add((cell_index(x, cell_size), cell_index(y, cell_size)))
    return cells
