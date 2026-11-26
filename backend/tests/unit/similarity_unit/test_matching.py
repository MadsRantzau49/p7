from collections.abc import Sequence

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
