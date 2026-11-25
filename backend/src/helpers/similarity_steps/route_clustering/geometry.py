import math
from itertools import pairwise

from models.similarity import Polyline


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
