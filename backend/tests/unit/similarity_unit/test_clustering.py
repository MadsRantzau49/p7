from collections.abc import Sequence

import pytest
from helpers.similarity_steps.route_clustering.clustering import cluster_routes
from models.similarity import ProjectedPoint, ProjectedRoute, ProjectedSubtrajectory


def _subtrajectory(
    trajectory_id: int, coordinates: Sequence[tuple[float, float]]
) -> ProjectedSubtrajectory:
    """Build a projected subtrajectory from (x, y) pairs in metres."""
    return ProjectedSubtrajectory(trajectory_id, [ProjectedPoint(x, y) for x, y in coordinates])


def _coordinates(route: ProjectedRoute) -> list[tuple[float, float]]:
    """Return a route's representative as (x, y) pairs."""
    return [(point.x, point.y) for point in route.points]


def test_two_identical_routes_give_one_route_with_count_two():
    """The second route joins the first instead of creating new geometry."""
    line = [(0, 0), (10, 0), (20, 0)]

    [route] = cluster_routes([_subtrajectory(1, line), _subtrajectory(2, line)], 1)

    assert _coordinates(route) == line
    assert route.count == 2


def test_reversed_route_gives_its_own_route():
    """Matching keeps order, so opposite directions of travel stay apart."""
    line = [(0, 0), (10, 0), (20, 0)]

    routes = cluster_routes([_subtrajectory(1, line), _subtrajectory(2, line[::-1])], 1)

    assert [route.count for route in routes] == [1, 1]


def test_routes_far_apart_give_separate_routes():
    """Routes with nothing in common stay on their own."""
    routes = cluster_routes(
        [_subtrajectory(1, [(0, 0), (10, 0)]), _subtrajectory(2, [(500, 500), (510, 500)])],
        1,
    )

    assert [route.count for route in routes] == [1, 1]


def test_longest_route_becomes_the_representative():
    """Among matching routes the longest provides the representative geometry."""
    straight = [(0, 0), (10, 0), (20, 0)]
    zigzag = [(0, 0), (5, 0.5), (10, 0), (15, 0.5), (20, 0)]

    [route] = cluster_routes([_subtrajectory(1, straight), _subtrajectory(2, zigzag)], 1)

    assert _coordinates(route) == zigzag
    assert route.count == 2


def test_route_diverging_in_the_middle_forms_its_own_route():
    """A trip that shares the ends but takes a different middle is a separate route now."""
    road = [(0, 0), (10, 0), (20, 0), (30, 0)]
    detour = [(0, 0), (10, 0), (20, 10), (30, 0)]

    routes = cluster_routes([_subtrajectory(1, road), _subtrajectory(2, detour)], 1)

    assert [route.count for route in routes] == [1, 1]


def test_repeated_trajectory_id_counts_as_one_route():
    """Two subtrajectories of the same source trajectory count as one contributor."""
    line = [(0, 0), (10, 0)]

    [route] = cluster_routes([_subtrajectory(7, line), _subtrajectory(7, line)], 1)

    assert route.count == 1


def test_only_stationary_routes_are_rejected():
    """Without a single moving segment there is nothing to cluster."""
    stationary = [(0, 0), (0, 0)]

    with pytest.raises(ValueError, match="No non-zero-length segments"):
        cluster_routes([_subtrajectory(1, stationary), _subtrajectory(2, stationary)], 0)


def test_empty_input_is_rejected():
    """No routes means there is nothing to cluster."""
    with pytest.raises(ValueError, match="No non-zero-length segments"):
        cluster_routes([], 1)
