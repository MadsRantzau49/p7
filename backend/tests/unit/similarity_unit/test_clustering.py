from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from itertools import permutations
from random import Random

import pytest
from helpers.similarity_steps.route_clustering import clustering
from helpers.similarity_steps.route_clustering.clustering import (
    assign_clusters,
    build_global_grid,
    build_polylines,
    cluster_routes,
    order_by_popularity,
)
from helpers.similarity_steps.route_clustering.geometry import polyline_cells
from helpers.similarity_steps.route_clustering.matching import MatchingCounts, routes_match
from models.similarity import Polyline, ProjectedPoint, ProjectedRoute, ProjectedSubtrajectory

MOMENT = datetime(2020, 1, 1, tzinfo=UTC)


def _subtrajectory(
    trajectory_id: int, coordinates: Sequence[tuple[float, float]], minute: int = 0
) -> ProjectedSubtrajectory:
    """Build a projected subtrajectory from (x, y) pairs; minute makes its times unique."""
    moment = MOMENT + timedelta(minutes=minute)
    return ProjectedSubtrajectory(
        trajectory_id, moment, moment, [ProjectedPoint(x, y) for x, y in coordinates]
    )


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


def test_route_diverging_in_the_middle_forms_its_own_route():
    """A trip that shares the ends but takes a different middle is a separate route."""
    road = [(0, 0), (10, 0), (20, 0), (30, 0)]
    detour = [(0, 0), (10, 0), (20, 10), (30, 0)]

    routes = cluster_routes([_subtrajectory(1, road), _subtrajectory(2, detour)], 1)

    assert [route.count for route in routes] == [1, 1]


def test_lone_subtrajectory_is_still_a_route_with_count_one():
    """A subtrajectory matching nothing is returned as its own route (F10)."""
    [route] = cluster_routes([_subtrajectory(1, [(0, 0), (10, 0), (20, 0)])], 1)

    assert route.count == 1


def test_representative_breaks_ties_on_the_lowest_trajectory_id():
    """When members share the same grid cells the lowest trajectory id provides the geometry."""
    anchor = [(0, 0), (20, 0)]
    joined = [(0, 0.3), (20, 0.3)]

    [route] = cluster_routes([_subtrajectory(5, anchor), _subtrajectory(2, joined)], 1)

    assert _coordinates(route) == joined
    assert route.count == 2


def test_members_list_every_grouped_subtrajectory():
    """Both subtrajectories of one trajectory are kept as members but counted once."""
    line = [(0, 0), (10, 0)]

    [route] = cluster_routes([_subtrajectory(7, line, minute=0), _subtrajectory(7, line, minute=5)], 1)

    assert route.count == 1
    assert [member.trajectory_id for member in route.members] == [7, 7]
    assert len({member.exit_a_time for member in route.members}) == 2


def test_popular_subtrajectory_is_processed_first_without_using_the_grid_as_a_match_filter():
    """A higher ID can lead the cluster, and an adjacent-cell route can still join it."""
    ids_and_heights = [(1, -0.25), (9, 0.5), (10, 0.6)]
    trips = [_subtrajectory(ident, [(0, y), (10, y)]) for ident, y in ids_and_heights]
    assert not polyline_cells(Polyline.from_points(trips[0].projected_points), 1) & polyline_cells(
        Polyline.from_points(trips[1].projected_points), 1
    )

    for order in permutations(trips):
        [route] = cluster_routes(list(order), 1)
        assert _coordinates(route) == [(0, 0.5), (10, 0.5)]
        assert [member.trajectory_id for member in route.members] == [9, 10, 1]


def test_repeated_segments_do_not_inflate_cell_popularity():
    """Each cell counts distinct subtrajectories, not segments or distinct original trips."""
    entries = build_polylines(
        [
            _subtrajectory(7, [(0.25, 0.25), (1.75, 0.25), (0.25, 0.25), (1.75, 0.25)]),
            _subtrajectory(7, [(0.25, 0.25), (1.75, 0.25)], minute=1),
        ]
    )

    grid = build_global_grid(entries, 1)
    assert grid is not None
    assert grid.popularity == {(0, 0): 2, (1, 0): 2}
    assert grid.cells_by_entry == [{(0, 0), (1, 0)}] * 2


def test_grid_uses_larger_cells_only_when_needed(monkeypatch):
    """Check the complete workload before walking the grid at the selected size."""
    monkeypatch.setattr(clustering, "MAX_GRID_CELL_VISITS", 6)
    line = [(0, 0), (2, 0)]
    entries = build_polylines([_subtrajectory(i, line) for i in range(3)])
    grid = build_global_grid(entries[:2], 1)
    assert grid is not None and grid.cell_size == 1
    assert sum(grid.popularity.values()) == 6

    def checked_grid_walk(polyline, size):
        assert size == 2, "Walked the grid before finding a size within budget"
        return polyline_cells(polyline, size)

    monkeypatch.setattr(clustering, "polyline_cells", checked_grid_walk)
    grid = build_global_grid(entries, 1)
    assert grid is not None and grid.cell_size == 2
    assert sum(grid.popularity.values()) == 6


def test_larger_popularity_cells_do_not_change_matching_distance(monkeypatch):
    """Even routes sharing all their coarser cells must pass the original Fréchet threshold."""
    monkeypatch.setattr(clustering, "MAX_GRID_CELL_VISITS", 6)
    trips = [
        _subtrajectory(1, [(0, 0), (100, 0)]),
        _subtrajectory(2, [(0, 0.5), (100, 0.5)]),
        _subtrajectory(3, [(0, 2), (100, 2)]),
    ]
    grid = build_global_grid(build_polylines(trips), 1)
    assert grid is not None and grid.cell_size > 2
    assert grid.cells_by_entry[0] == grid.cells_by_entry[2]
    routes = cluster_routes(trips, 1)
    assert [[member.trajectory_id for member in route.members] for route in routes] == [[1, 2], [3]]


def test_matching_still_runs_when_no_popularity_grid_fits(monkeypatch):
    """Even with no affordable grid, exact matching processes every piece."""
    monkeypatch.setattr(clustering, "MAX_GRID_CELL_VISITS", 1)
    line = [(0, 0), (2, 0)]
    trips = [_subtrajectory(i, line) for i in range(2)]
    assert build_global_grid(build_polylines(trips), 1) is None
    [route] = cluster_routes(trips, 1)
    assert route.count == 2


def test_popularity_excludes_the_subtrajectory_itself():
    """A long route that overlaps nobody does not win just because it visits more cells."""
    entries = build_polylines(
        [
            _subtrajectory(1, [(0, 5), (20, 5)]),
            _subtrajectory(2, [(0, 0.1), (2, 0.1)]),
            _subtrajectory(3, [(0, 0.2), (2, 0.2)]),
        ]
    )
    ordered = order_by_popularity(entries, build_global_grid(entries, 1))
    assert [entry.member.trajectory_id for entry in ordered] == [2, 3, 1]


def test_same_trajectory_tie_breaks_on_crossing_times():
    """Later pieces of the same trajectory do not win equal scores based on input order."""
    earlier = _subtrajectory(7, [(0, 0.2), (10, 0.2)])
    later = _subtrajectory(7, [(0, 0.3), (10, 0.3)], minute=1)

    for order in ([later, earlier], [earlier, later]):
        [route] = cluster_routes(order, 1)
        assert _coordinates(route) == [(0, 0.2), (10, 0.2)]
        assert route.count == 1


def test_members_match_the_permanent_representative_not_the_last_member():
    """A bridge route cannot pull a cluster away from its original representative."""
    trips = [
        _subtrajectory(3, [(0, 1.6), (10, 1.6)]),
        _subtrajectory(2, [(0, 0.85), (10, 0.85)]),
        _subtrajectory(1, [(0, 0.1), (10, 0.1)]),
    ]
    routes = cluster_routes(trips, 1)
    assert [[member.trajectory_id for member in route.members] for route in routes] == [[1, 2], [3]]
    assert _coordinates(routes[0]) == [(0, 0.1), (10, 0.1)]

    points_by_id = {trip.trajectory_id: trip.projected_points for trip in trips}
    for route in routes:
        representative = Polyline.from_points(route.points)
        for member in route.members:
            member_line = Polyline.from_points(points_by_id[member.trajectory_id])
            assert routes_match(member_line, representative, 1)


def test_assignment_uses_the_first_matching_representative():
    """An entry matching two representatives joins the earlier one even if farther away."""
    entries = build_polylines(
        [
            _subtrajectory(1, [(0, 0), (10, 0)]),
            _subtrajectory(2, [(0, 1.5), (10, 1.5)]),
            _subtrajectory(3, [(0, 0.9), (10, 0.9)]),
        ]
    )
    first, second = assign_clusters(entries, 1)
    assert first.representative is entries[0].polyline
    assert second.representative is entries[1].polyline
    assert [member.trajectory_id for member in first.members] == [1, 3]


def test_start_index_keeps_cluster_order_across_buckets():
    """The first matching representative wins even when a later bucket is searched first."""
    entries = build_polylines(
        [
            _subtrajectory(1, [(0.75, 0), (10.75, 0)]),
            _subtrajectory(2, [(-0.75, 0), (9.25, 0)]),
            _subtrajectory(3, [(0, 0), (10, 0)]),
        ]
    )
    clusters = assign_clusters(entries, 1)
    assert [[member.trajectory_id for member in cluster.members] for cluster in clusters] == [[1, 3], [2]]


def test_prefilters_skip_impossible_matches_but_keep_exact_boundary_matches():
    """Reject distant starts and detours; two routes exactly epsilon apart still match."""
    entries = build_polylines(
        [
            _subtrajectory(1, [(0, 0), (10, 0)]),
            _subtrajectory(2, [(0, -1), (10, -1)]),
            _subtrajectory(3, [(0, 0), (5, 3), (10, 0)]),
            _subtrajectory(4, [(100, 0), (110, 0)]),
        ]
    )
    counts = MatchingCounts()
    clusters = assign_clusters(entries, 1, counts)
    member_ids = [[member.trajectory_id for member in cluster.members] for cluster in clusters]
    assert member_ids == [[1, 2], [3], [4]]
    assert counts.endpoint_bucket_skips == 2
    assert counts.bounds_rejections == counts.successful_matches == 1


def test_prefilters_agree_with_exhaustive_assignment():
    """Compare the indexed pass to checking every representative in the same order."""
    rng = Random(860)
    trips = [
        _subtrajectory(i, [(x, offsets[0]), (x + 5, offsets[1]), (x + 10, offsets[2])])
        for i, (x, offsets) in enumerate(
            (rng.randint(-12, 12) / 2, [rng.randint(-4, 4) / 2 for _ in range(3)]) for _ in range(160)
        )
    ]
    for epsilon in (0.5, 1, 2, 4):
        entries = build_polylines(trips)
        ranked = order_by_popularity(entries, build_global_grid(entries, epsilon))
        exhaustive = []
        for entry in ranked:
            for representative, members in exhaustive:
                if routes_match(entry.polyline, representative, epsilon):
                    members.append(entry.member)
                    break
            else:
                exhaustive.append((entry.polyline, [entry.member]))

        clusters = assign_clusters(ranked, epsilon)
        assert [(cluster.representative, cluster.members) for cluster in clusters] == exhaustive


@pytest.mark.parametrize(("epsilon", "expected_counts"), [(0, [2, 1]), (-1, [1, 1, 1])])
def test_nonpositive_epsilon_keeps_historical_behavior(epsilon, expected_counts):
    """Zero matches exact routes in input order; negative epsilon matches no pair."""
    trips = [
        _subtrajectory(9, [(0, 0), (10, 0)]),
        _subtrajectory(1, [(0, 0), (10, 0)]),
        _subtrajectory(2, [(0, 0.1), (10, 0.1)]),
    ]
    routes = cluster_routes(trips, epsilon)
    assert [route.count for route in routes] == expected_counts
    assert routes[0].members[0].trajectory_id == 9


def test_nan_epsilon_is_rejected():
    """NaN cannot define spatial grid cells."""
    with pytest.raises(ValueError, match="Epsilon must not be NaN"):
        cluster_routes([_subtrajectory(1, [(0, 0), (10, 0)])], float("nan"))


def test_only_stationary_routes_are_rejected():
    """Without a single moving segment there is nothing to cluster."""
    stationary = [(0, 0), (0, 0)]

    with pytest.raises(ValueError, match="No non-zero-length segments"):
        cluster_routes([_subtrajectory(1, stationary), _subtrajectory(2, stationary)], 1)


def test_empty_input_is_rejected():
    """No routes means there is nothing to cluster."""
    with pytest.raises(ValueError, match="No non-zero-length segments"):
        cluster_routes([], 1)
