import pytest
from helpers.similarity_steps.pathlet_extension.representative_grid import RepresentativeGrid
from models.similarity import Polyline, ProjectedPoint, Representative, TrajectorySection

EPSILON = 1.0
CELL_SIZE = 10.0


def _representative(coordinates: list[tuple[float, float]]) -> Representative:
    """Build a representative from (x, y) pairs in metres."""
    polyline = Polyline.from_points([ProjectedPoint(x, y) for x, y in coordinates])
    return Representative(polyline, TrajectorySection(1, 0.0, polyline.total_length))


def _grid_with(coordinates: list[tuple[float, float]]) -> tuple[RepresentativeGrid, Representative]:
    """Build a grid that holds one representative."""
    grid = RepresentativeGrid(EPSILON, CELL_SIZE)
    representative = _representative(coordinates)
    grid.add(representative)
    return grid, representative


def test_point_within_epsilon_gives_a_seed_describing_the_closest_spot():
    """A seed records the segment, where on it the point is closest, and how far away it is."""
    grid, representative = _grid_with([(0, 0), (10, 0)])

    [seed] = grid.seeds_near(ProjectedPoint(5, -0.5))

    assert seed.representative is representative
    assert seed.segment_index == 0
    assert seed.fraction == 0.5
    assert seed.distance_squared == pytest.approx(0.25)


def test_point_exactly_epsilon_away_gives_a_seed():
    """The epsilon bound is inclusive."""
    grid, _ = _grid_with([(0, 0), (10, 0)])

    assert len(grid.seeds_near(ProjectedPoint(5, 1))) == 1


def test_point_further_than_epsilon_gives_no_seed():
    """A point outside the expanded box is rejected."""
    grid, _ = _grid_with([(0, 0), (10, 0)])

    assert grid.seeds_near(ProjectedPoint(5, 2)) == []


def test_point_in_the_box_corner_but_further_than_epsilon_gives_no_seed():
    """The box is only a quick filter: (11, 1) is inside it but about 1.41 m from the segment."""
    grid, _ = _grid_with([(0, 0), (10, 0)])

    assert grid.seeds_near(ProjectedPoint(11, 1)) == []


def test_point_at_a_corner_gives_a_seed_for_both_segments():
    """The corner of an L-shape belongs to the two segments that meet there."""
    grid, _ = _grid_with([(0, 0), (10, 0), (10, 10)])

    seeds = grid.seeds_near(ProjectedPoint(10, 0))

    assert sorted(seed.segment_index for seed in seeds) == [0, 1]


def test_segment_in_negative_coordinates_is_found():
    """Cells are floored, so coordinates below zero land in the right cell."""
    grid, _ = _grid_with([(-20, -5), (-10, -5)])

    assert grid.cell_coordinate(-0.1) == -1
    assert len(grid.seeds_near(ProjectedPoint(-15, -5))) == 1
