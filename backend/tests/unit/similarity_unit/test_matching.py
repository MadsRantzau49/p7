from collections.abc import Sequence

from helpers.similarity_steps.route_clustering import matching
from helpers.similarity_steps.route_clustering.matching import routes_match
from models.similarity import Polyline, ProjectedPoint

Coordinates = Sequence[tuple[float, float]]

EPSILON = 1.0


def _polyline(coordinates: Coordinates) -> Polyline:
    """Build a polyline from (x, y) pairs in metres."""
    return Polyline.from_points([ProjectedPoint(x, y) for x, y in coordinates])


def test_identical_routes_match():
    """A route always matches itself."""
    line = _polyline([(0, 0), (10, 0), (20, 0)])

    assert routes_match(line, line, EPSILON)


def test_parallel_routes_within_epsilon_match():
    """Two routes a little closer than epsilon apart are the same route."""
    first = _polyline([(0, 0), (10, 0), (20, 0)])
    second = _polyline([(0, 0.5), (10, 0.5), (20, 0.5)])

    assert routes_match(first, second, EPSILON)


def test_parallel_routes_beyond_epsilon_do_not_match():
    """Two routes further than epsilon apart are different routes."""
    first = _polyline([(0, 0), (10, 0), (20, 0)])
    second = _polyline([(0, 2), (10, 2), (20, 2)])

    assert not routes_match(first, second, EPSILON)


def test_a_single_stretch_beyond_epsilon_keeps_routes_apart():
    """Close for most of the way, but one stretch too far apart, so not the same route."""
    straight = _polyline([(0, 0), (10, 0), (20, 0)])
    detour = _polyline([(0, 0), (10, 5), (20, 0)])

    assert not routes_match(straight, detour, EPSILON)


def test_reversed_route_does_not_match():
    """Matching keeps order, so opposite directions of travel stay apart."""
    line = [(0, 0), (10, 0), (20, 0)]
    forward = _polyline(line)
    backward = _polyline(line[::-1])

    assert not routes_match(forward, backward, EPSILON)


def test_routes_match_despite_different_sampling():
    """The same path recorded with different points still matches."""
    sparse = _polyline([(0, 0), (20, 0)])
    dense = _polyline([(0, 0), (5, 0), (10, 0), (15, 0), (20, 0)])

    assert routes_match(sparse, dense, EPSILON)


def test_a_longer_route_does_not_match_a_shorter_prefix():
    """A route that continues past where another ends is not the same route."""
    short = _polyline([(0, 0), (10, 0)])
    long = _polyline([(0, 0), (10, 0), (20, 0)])

    assert not routes_match(short, long, EPSILON)


def test_long_parallel_routes_skip_unreachable_cells():
    """A narrow corridor through the diagram does not require visiting the entire grid."""
    first = _polyline([(10 * i, 0) for i in range(200)])
    second = _polyline([(10 * i, 0.5) for i in range(200)])
    matches, visited = matching._reachable_end(first, second, 0.5)
    assert matches
    assert 199 <= visited < 4 * 199


def test_routes_can_follow_a_starting_wall_for_several_segments():
    """Matching may hold one endpoint still while the other route begins moving."""
    first = _polyline([(0, 0), (10, 0)])
    second = _polyline([(0, 0), (0, 0.5), (0, 0.5), (0.25, 0.5), (10, 0)])

    assert routes_match(first, second, EPSILON)
    assert routes_match(second, first, EPSILON)


def test_matching_rejects_backtracking_despite_identical_endpoints_and_extent():
    """Reachability still enforces travel order even when the geometry overlaps exactly."""
    direct = _polyline([(0, 0), (10, 0)])
    backtracking = _polyline([(0, 0), (10, 0), (0, 0), (10, 0)])

    assert not routes_match(direct, backtracking, EPSILON)
    assert not routes_match(backtracking, direct, EPSILON)


def test_matching_can_require_a_later_meeting():
    """An alternative forward walk can succeed when the earliest meetings do not."""
    first = _polyline([(0, 0), (2, 0), (2, -1), (1, 0), (4, 0)])
    second = _polyline([(0, 0), (1, 0), (1, 1), (3, -1), (4, 0)])
    assert routes_match(first, second, EPSILON)
