from collections.abc import Sequence

import pytest
from helpers.similarity_steps.pathlet_extension.matching import (
    BACKWARD,
    FORWARD,
    _advance,
    _corners_within_epsilon,
    _rank_seeds,
    find_match,
)
from helpers.similarity_steps.pathlet_extension.representative_grid import RepresentativeGrid
from models.similarity import Polyline, ProjectedPoint, Representative, TrajectorySection

Coordinates = Sequence[tuple[float, float]]

EPSILON = 1.0
STRAIGHT_LINE = [(0, 0), (10, 0), (20, 0)]
L_SHAPE = [(0, 0), (10, 0), (10, 10)]
ALIGNED_LINE = [(-10, 0.5), (10, 0.5)]
CROSSING_LINE = [(0, -20), (0, 20)]


def _polyline(coordinates: Coordinates) -> Polyline:
    """Build a polyline from (x, y) pairs in metres."""
    return Polyline.from_points([ProjectedPoint(x, y) for x, y in coordinates])


def _grid_with(*representative_lines: Coordinates) -> tuple[RepresentativeGrid, list[Representative]]:
    """Build a grid holding one representative per list of coordinates."""
    grid = RepresentativeGrid(EPSILON, 10.0)
    representatives = []
    for coordinates in representative_lines:
        polyline = _polyline(coordinates)
        representative = Representative(polyline, TrajectorySection(1, 0.0, polyline.total_length))
        grid.add(representative)
        representatives.append(representative)
    return grid, representatives


def _advance_along(representative_line: Coordinates, trajectory_line: Coordinates, direction: int):
    """Run _advance from the first trajectory point, seeded on the only nearby representative segment."""
    grid, _ = _grid_with(representative_line)
    trajectory = _polyline(trajectory_line)
    [seed] = grid.seeds_near(trajectory.points[0])
    return _advance(trajectory, 0, seed, direction, EPSILON)


# find_match


def test_find_match_returns_the_match_on_the_best_ranked_representative():
    """The crossing representative is closer and would also accept this short segment."""
    grid, [_, aligned] = _grid_with(CROSSING_LINE, ALIGNED_LINE)

    match = find_match(_polyline([(0, 0), (0.5, 0)]), 0, grid)

    assert match is not None
    assert match.representative is aligned


def test_find_match_returns_none_when_no_representative_is_nearby():
    """Without a seed near the start point there is nothing to match."""
    grid, _ = _grid_with(STRAIGHT_LINE)

    assert find_match(_polyline([(500, 500), (510, 500)]), 0, grid) is None


# _rank_seeds


def test_rank_seeds_puts_an_aligned_representative_before_a_closer_crossing_one():
    """Alignment outranks distance, and a segment running the opposite way prefers going backward."""
    grid, [crossing, aligned] = _grid_with(CROSSING_LINE, ALIGNED_LINE)
    trajectory = _polyline([(0, 0), (-0.5, 0)])

    ranked = _rank_seeds(grid.seeds_near(trajectory.points[0]), trajectory, 0, EPSILON)

    (first_seed, first_direction), (second_seed, _) = ranked
    assert first_seed.representative is aligned
    assert first_direction == BACKWARD
    assert second_seed.representative is crossing


# _advance


def test_advance_forward_follows_the_whole_representative():
    """An identical trajectory is accepted from the first representative point to the last."""
    match = _advance_along(STRAIGHT_LINE, STRAIGHT_LINE, FORWARD)

    assert match is not None
    assert match.end_index == 2
    assert (match.start_m, match.end_m) == (0, 20)


def test_advance_backward_walks_towards_the_start_of_the_representative():
    """A backward match begins at the far end, so start_m is larger than end_m."""
    match = _advance_along(STRAIGHT_LINE, STRAIGHT_LINE[::-1], BACKWARD)

    assert match is not None
    assert match.end_index == 2
    assert (match.start_m, match.end_m) == (20, 0)


def test_advance_stops_at_the_first_segment_that_leaves_the_representative():
    """The match is one continuous run that ends where the trajectory turns away."""
    match = _advance_along(STRAIGHT_LINE, L_SHAPE, FORWARD)

    assert match is not None
    assert match.end_index == 1
    assert match.end_m == 10


def test_advance_returns_none_when_the_first_segment_cuts_a_corner():
    """Reaching the far end is not enough if the corner passed on the way is too far away."""
    assert _advance_along(L_SHAPE, [(0, 0), (10, 10)], FORWARD) is None


# _corners_within_epsilon


@pytest.mark.parametrize(
    ("epsilon_squared", "accepted"),
    [(112.5, True), (112.0, False)],
)
def test_corners_within_epsilon_uses_steady_pace_pairing(
    epsilon_squared,
    accepted,
):
    """Steady pacing."""
    result = _corners_within_epsilon(
        _polyline([(0, 0), (10, 0), (10, 30)]),
        range(1, 2),
        0.0,
        40.0,
        ProjectedPoint(0, 0),
        ProjectedPoint(10, 30),
        epsilon_squared,
    )

    assert result is accepted
