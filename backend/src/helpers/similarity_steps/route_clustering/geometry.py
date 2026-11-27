import math

from models.similarity import Polyline, ProjectedPoint

Cell = tuple[int, int]
GridPoint = tuple[int, int, int]


def cell_index(value: float, cell_size: float) -> int:
    """Index of the grid column or row that contains a coordinate."""
    if math.isinf(cell_size):
        return 0
    return _cell_index(value, cell_size, cell_size.as_integer_ratio())


def _cell_index(value: float, cell_size: float, size_ratio: tuple[int, int]) -> int:
    quotient = value / cell_size
    # A rounded quotient cannot cross an integer boundary without landing on it.
    if not quotient.is_integer() and math.isfinite(quotient):
        return math.floor(quotient)
    num, den = value.as_integer_ratio()
    size, size_den = size_ratio
    return (num * size_den) // (den * size)


def _grid_point(point: ProjectedPoint, cell_ratio: tuple[int, int]) -> GridPoint:
    """Express both axes in cell units using a common integer denominator."""
    x, x_den = point.x.as_integer_ratio()
    y, y_den = point.y.as_integer_ratio()
    size, size_den = cell_ratio
    den = max(x_den, y_den)  # Float denominators are powers of two.
    return x * (den // x_den) * size_den, y * (den // y_den) * size_den, den * size


def _add_segment_cells(
    cells: set[Cell], start: GridPoint, end: GridPoint, start_cell: Cell, end_cell: Cell
) -> None:
    """Walk crossings in parametric order rather than sampling along the segment."""
    x, y = start_cell
    end_x, end_y = end_cell
    step_x = 1 if end_x > x else -1
    step_y = 1 if end_y > y else -1

    if y == end_y:
        cells.update((column, y) for column in range(x + step_x, end_x + step_x, step_x))
        return
    if x == end_x:
        cells.update((x, row) for row in range(y + step_y, end_y + step_y, step_y))
        return

    # The denominators differ only by powers of two; convert to the finer unit.
    den = max(start[2], end[2])
    a = den // start[2]
    b = den // end[2]
    sx, sy = start[0] * a, start[1] * a
    dx, dy = abs(end[0] * b - sx), abs(end[1] * b - sy)
    # Compare crossing parameters by cross multiplication, exactly, even near a corner.
    next_x = abs((x + (step_x > 0)) * den - sx) * dy
    next_y = abs((y + (step_y > 0)) * den - sy) * dx
    delta_x, delta_y = den * dy, den * dx

    while x != end_x and y != end_y:
        if next_x < next_y:
            x += step_x
            next_x += delta_x
        elif next_y < next_x:
            y += step_y
            next_y += delta_y
        else:
            if step_x != step_y:
                # A corner belongs to the cell on its positive side on both axes.
                cells.add((x + (step_x > 0), y + (step_y > 0)))
            x += step_x
            y += step_y
            next_x += delta_x
            next_y += delta_y
        cells.add((x, y))

    cells.update((column, y) for column in range(x + step_x, end_x + step_x, step_x))
    cells.update((x, row) for row in range(y + step_y, end_y + step_y, step_y))


def polyline_cell_visit_bound(polyline: Polyline, cell_size: float) -> int:
    """Bound the number of cell visits from the vertices, without walking the grid."""
    if not cell_size > 0:
        raise ValueError("Grid cell size must be positive.")
    points = iter(polyline.points)
    first = next(points, None)
    if first is None:
        return 0
    if math.isinf(cell_size):
        return 1

    ratio = cell_size.as_integer_ratio()
    x = _cell_index(first.x, cell_size, ratio)
    y = _cell_index(first.y, cell_size, ratio)
    visits = 1
    for point in points:
        next_x = _cell_index(point.x, cell_size, ratio)
        next_y = _cell_index(point.y, cell_size, ratio)
        # A segment visits at most one extra cell per crossed grid line.
        # Even at a corner, at most two cells are added for the two crossings.
        visits += abs(next_x - x) + abs(next_y - y)
        x, y = next_x, next_y
    return visits


def polyline_cells(polyline: Polyline, cell_size: float) -> set[Cell]:
    """Return the distinct cells containing points anywhere along the polyline.

    Cells are half-open on both axes, so a point on a boundary belongs to one cell,
    the one chosen by floor division. A segment on a grid line does not count on both sides.
    """
    if not cell_size > 0:
        raise ValueError("Grid cell size must be positive.")
    points = iter(polyline.points)
    start = next(points, None)
    if start is None:
        return set()
    if math.isinf(cell_size):
        return {(0, 0)}

    size_ratio = cell_size.as_integer_ratio()
    start_cell = (_cell_index(start.x, cell_size, size_ratio), _cell_index(start.y, cell_size, size_ratio))
    exact_start = None
    cells = {start_cell}
    for end in points:
        end_cell = (_cell_index(end.x, cell_size, size_ratio), _cell_index(end.y, cell_size, size_ratio))
        exact_end = None
        if start_cell != end_cell:
            if abs(start_cell[0] - end_cell[0]) + abs(start_cell[1] - end_cell[1]) == 1:
                cells.add(end_cell)  # A segment between edge-neighbouring cells can only visit those two.
            else:
                exact_end = _grid_point(end, size_ratio)
                _add_segment_cells(
                    cells, exact_start or _grid_point(start, size_ratio), exact_end, start_cell, end_cell
                )
        start, start_cell, exact_start = end, end_cell, exact_end
    return cells
