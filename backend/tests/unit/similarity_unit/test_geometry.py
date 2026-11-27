import pytest
from helpers.similarity_steps.route_clustering.geometry import (
    cell_index,
    polyline_cell_visit_bound,
    polyline_cells,
)
from models.similarity import Polyline, ProjectedPoint

ORIGIN = ProjectedPoint(0, 0)


def test_polyline_cells_cover_a_segment_without_gaps():
    """A 25 m segment over 10 m cells touches columns 0, 1 and 2 with no cell skipped."""
    polyline = Polyline.from_points([ORIGIN, ProjectedPoint(25, 0)])

    cells = polyline_cells(polyline, 10)

    assert cells == {(0, 0), (1, 0), (2, 0)}


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        ((0.25, 0.5), (1.5, 1.25), {(0, 0), (1, 0), (1, 1)}),
        ((0.25, 0.25), (1.75, 1.75), {(0, 0), (1, 1)}),
        ((0.25, 1.75), (1.75, 0.25), {(0, 1), (1, 1), (1, 0)}),
        ((-1.5, -1), (1, -1), {(-2, -1), (-1, -1), (0, -1), (1, -1)}),
        ((-1, 0), (-1, -0.5), {(-1, 0), (-1, -1)}),
        ((1, 1), (0.75, 1.25), {(1, 1), (0, 1)}),
        ((0.25, 0.25), (1.75, 1.7500000000000002), {(0, 0), (0, 1), (1, 1)}),
        ((0.25, 0.25), (0.25, 0.25), {(0, 0)}),
    ],
)
def test_grid_crossings_in_both_directions(start, end, expected):
    """Visit all intervening cells, with the same half-open boundaries in either direction."""
    points = [ProjectedPoint(*start), ProjectedPoint(*end)]
    assert polyline_cells(Polyline.from_points(points), 1) == expected
    assert polyline_cells(Polyline.from_points(points[::-1]), 1) == expected
    assert polyline_cell_visit_bound(Polyline.from_points(points), 1) >= len(expected)
    assert polyline_cell_visit_bound(Polyline.from_points(points[::-1]), 1) >= len(expected)


def test_grid_cells_are_independent_of_sampling_density():
    """Splitting and retracing a segment does not add extra cells."""
    sparse = [(0.25, 1.75), (1.75, 0.25)]
    dense = [sparse[0], (1, 1), sparse[1], (1, 1), sparse[0]]
    assert polyline_cells(Polyline.from_points([ProjectedPoint(*p) for p in sparse]), 1) == polyline_cells(
        Polyline.from_points([ProjectedPoint(*p) for p in dense]), 1
    )


def test_grid_index_uses_exact_cell_when_division_rounds_to_integer():
    """The represented cell size 0.1 is slightly larger than one tenth."""
    assert cell_index(1, 0.1) == 9
    assert cell_index(-1, 0.1) == -10


def test_grid_visit_bound_counts_retracing_and_handles_empty_polylines():
    """The budget bounds work, not only the number of distinct cells retained."""
    line = Polyline.from_points([ORIGIN, ProjectedPoint(2, 0), ORIGIN])
    assert len(polyline_cells(line, 1)) == 3
    assert polyline_cell_visit_bound(line, 1) == 5
    assert polyline_cell_visit_bound(line, float("inf")) == 1
    assert polyline_cell_visit_bound(Polyline.from_points([]), 1) == 0
