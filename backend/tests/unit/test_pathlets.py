"""Exact metric examples exercise each replaceable clustering stage."""

from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime, timedelta
from math import hypot
from pathlib import Path

import pytest
from models.uniformed_trajectories import UniformedTrajectories, UniformedTrajectoryPoint
from models.upload_row import VehicleType
from pathlets.extension import extend_clusters, generate_overlap_atoms
from pathlets.geometry import (
    convert_to_meters,
    generate_segments,
    interval_coordinates,
    length,
    point_segment_distance,
    sspd,
)
from pathlets.loading import from_uniformed, load_trajectories
from pathlets.models import (
    XY,
    Assignment,
    ClusteringConfig,
    ExtendedPathletCandidate,
    GPSTrajectory,
    MetricPathlet,
    MetricTrajectory,
)
from pathlets.selection import convert_to_gps, select_final_pathlets, uncovered_intervals, validate_coverage
from pathlets.spatial import (
    build_spatial_index,
    compare_sspd,
    construct_candidate_clusters,
    find_nearby_pairs,
)

EPOCH = datetime(2024, 1, 1)


def metric(trajectory_id: str, coordinates: Sequence[XY], day: int = 0) -> MetricTrajectory:
    """Construct a source trajectory whose time axis is independent of other cars."""
    return MetricTrajectory(
        trajectory_id,
        tuple(coordinates),
        tuple(EPOCH + timedelta(days=day, seconds=i) for i in range(len(coordinates))),
    )


def cluster(trajectories: list[MetricTrajectory], epsilon: float = 0.0):
    """Exercise the actual metric stages without projection noise in exact examples."""
    config = ClusteringConfig(Path("unused.csv"), epsilon_m=epsilon)
    segments = generate_segments(trajectories)
    pairs = find_nearby_pairs(segments, build_spatial_index(segments), config)
    matches = compare_sspd(pairs, segments, epsilon)
    clusters = construct_candidate_clusters(segments, matches)
    extended = extend_clusters(clusters, trajectories, segments, pairs, config)
    selected = select_final_pathlets(extended, trajectories, config)
    validate_coverage(selected, trajectories)
    return selected


def test_projection_roundtrip_and_duplicate_provenance():
    """Projection preserves ordered points, source rows, and exact stationary edges."""
    points = tuple(
        UniformedTrajectoryPoint(lon, EPOCH + timedelta(seconds=i), lat)
        for i, (lon, lat) in enumerate([(9.9, 57.0), (9.9, 57.0), (9.3, 54.8)])
    )
    source = GPSTrajectory("csv-id", points, (2, 3, 4))
    trajectories, projection = convert_to_meters([source])
    trajectory = trajectories[0]
    assert trajectory.trajectory_id == "csv-id"
    assert trajectory.timestamps == tuple(p.point_timestamp for p in points)
    assert trajectory.source_rows == (2, 3, 4)
    segments = generate_segments(trajectories)
    assert len(segments) == 2
    assert segments[0].start == segments[0].end
    assert segments[0].point_indices == (0, 1)
    assert segments[1].segment_index == 1
    assignment = Assignment("csv-id", 0, 2)
    output = convert_to_gps(
        [MetricPathlet("p", assignment, trajectory.coordinates, (assignment,), 0)], trajectories, projection
    )[0]
    for actual, expected in zip(output.coordinates, points, strict=True):
        assert actual == pytest.approx((expected.latitude, expected.longitude), abs=1e-9)
    assert output.assignments[0].start_timestamp == EPOCH
    assert output.assignments[0].source_rows == (2, 3, 4)
    assert 100_000 < projection.max_radius_m < 200_000


def test_projection_handles_antimeridian_and_rejects_global_extent():
    """A local dateline crossing works; arbitrary long journeys require partitioning."""

    def source(points):
        return [GPSTrajectory("a", tuple(UniformedTrajectoryPoint(lon, EPOCH, lat) for lon, lat in points))]

    projected, projection = convert_to_meters(source([(179.9, 20), (-179.9, 20)]))
    assert abs(projection.center_longitude) == pytest.approx(180)
    assert length(projected[0].coordinates) == pytest.approx(20_929.4, abs=1)
    with pytest.raises(ValueError, match="partition"):
        convert_to_meters(source([(0, 0), (120, 50)]))
    with pytest.raises(ValueError, match="finite valid"):
        convert_to_meters(source([(0, 0), (float("nan"), 0)]))


def test_segment_ids_bounds_and_timestamps():
    """Bounds are coordinate-order independent, and IDs never conflate trajectories."""
    segments = generate_segments(
        [metric("b", [(5, -2), (-3, 4), (-3, 4)]), metric("a", [(0, 0), (1, 1)], day=7)]
    )
    assert [s.segment_id for s in segments] == [0, 1, 2]
    assert [s.trajectory_id for s in segments] == ["b", "b", "a"]
    assert segments[0].bounds == (-3, -2, 5, 4)
    assert segments[1].bounds == (-3, 4, -3, 4)
    assert segments[2].timestamps == (EPOCH + timedelta(days=7), EPOCH + timedelta(days=7, seconds=1))


def test_rtree_matches_bruteforce_oracle_across_internal_groups():
    """Bulk-loaded overlapping tree branches cannot hide nearby candidate pairs."""
    trajectories = [metric(str(i), [(i * 2, 0), (i * 2 + 25, 10)]) for i in range(48)]
    trajectories += [metric("same", [(0, 2), (20, 2), (40, 2), (60, 2)])]
    segments = list(reversed(generate_segments(trajectories)))  # Tree positions differ from IDs.
    config = ClusteringConfig(Path("unused"), epsilon_m=1)
    pairs = find_nearby_pairs(segments, build_spatial_index(segments), config)
    oracle = []
    for first in segments:
        for second in segments:
            if first.segment_id >= second.segment_id or first.trajectory_id == second.trajectory_id:
                continue
            ax0, ay0, ax1, ay1 = first.bounds
            bx0, by0, bx1, by1 = second.bounds
            if ax0 - 4 <= bx1 and bx0 <= ax1 + 4 and ay0 - 4 <= by1 and by0 <= ay1 + 4:
                oracle.append((first.segment_id, second.segment_id))
    assert pairs == sorted(oracle)
    assert len(pairs) == len(set(pairs))
    assert all(a < b for a, b in pairs)


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        (((0, 0), (10, 0)), ((0, 3), (10, 3)), 3),
        (((0, 0), (10, 0)), ((5, 0), (15, 0)), 2.5),
        (((0, 0), (10, 0)), ((2, 0), (8, 0)), 1),
        (((-1, 0), (1, 0)), ((0, -1), (0, 1)), 1),
        (((0, 0), (0, 0)), ((3, 4), (3, 4)), 5),
        (((0, 0), (5, 0), (10, 0)), ((0, 0), (10, 0)), 0),
    ],
)
def test_exact_sspd(first, second, expected):
    """Known values use endpoint-to-segment distance, not vertex-to-vertex distance."""
    assert sspd(first, second) == pytest.approx(expected)
    assert sspd(second, first) == pytest.approx(expected)
    assert point_segment_distance((5, 3), (0, 0), (10, 0)) == 3
    with pytest.raises(ValueError):
        sspd((), first)


def test_threshold_equality_and_just_above():
    """The SSPD threshold is inclusive with no undocumented distance tolerance."""
    trajectories = [
        metric("a", [(0, 0), (10, 0)]),
        metric("b", [(0, 2), (10, 2)]),
        metric("c", [(0, 2.000001), (10, 2.000001)]),
    ]
    segments = generate_segments(trajectories)
    matches = compare_sspd([(0, 1), (0, 2)], segments, 2)
    assert [(m.first_id, m.second_id, m.distance_m) for m in matches] == [(0, 1, 2)]


def test_representative_stars_do_not_chain_and_count_distinct_sources():
    """A~B and B~C do not imply A~C; repeated B segments count once."""
    trajectories = [
        metric("a", [(0, 0), (10, 0)]),
        metric("b", [(0, 1), (10, 1), (0, 1)]),
        metric("c", [(0, 2), (10, 2)]),
    ]
    segments = generate_segments(trajectories)
    pairs = find_nearby_pairs(
        segments, build_spatial_index(segments), ClusteringConfig(Path("x"), epsilon_m=1)
    )
    clusters = construct_candidate_clusters(segments, compare_sspd(pairs, segments, 1))
    assert clusters[0].member_ids == (0, 1, 2)
    assert clusters[0].trajectory_ids == ("a", "b")
    assert clusters[1].trajectory_ids == ("a", "b", "c")
    assert clusters[3].trajectory_ids == ("b", "c")


def test_consecutive_extension_without_timestamp_alignment():
    """Matching paths merge into one interval despite unrelated recording dates."""
    coordinates = [(0, 0), (10, 0), (20, 0), (30, 0)]
    output = cluster([metric("a", coordinates), metric("b", coordinates, day=50)])
    assert len(output) == 1
    assert output[0].assignments == (Assignment("a", 0, 3), Assignment("b", 0, 3))
    assert output[0].coordinates == tuple(coordinates)


def test_unequal_sampling_and_partial_source_endpoints():
    """Whole-segment failures still seed shared fractional, multi-sample intervals."""
    trajectories = [metric("a", [(0, 0), (10, 0), (20, 0)]), metric("b", [(2, 0), (4, 0), (13, 0), (18, 0)])]
    assert compare_sspd([(0, 2)], generate_segments(trajectories), 0) == []
    output = cluster(trajectories, 1e-8)
    shared = [p for p in output if len(p.assignments) == 2]
    assert len(shared) == 1
    assert shared[0].assignments == (Assignment("a", 0.2, 1.8), Assignment("b", 0, 3))
    assert shared[0].coordinates == ((2, 0), (10, 0), (18, 0))
    singleton_lengths = [length(p.coordinates) for p in output if len(p.assignments) == 1]
    assert singleton_lengths == [2, 2]


def test_divergence_rejoining_and_complete_singleton_branch():
    """Support is three, then two, then three, with one complete unique branch."""
    common = [(i * 10, 0) for i in range(6)]
    branch = [(0, 0), (10, 0), (20, 20), (30, 20), (40, 0), (50, 0)]
    trajectories = [metric("a", common), metric("b", common), metric("c", branch)]
    output = cluster(trajectories)
    assert len(output) == 4
    shared = sorted(
        (p.representative.start, p.representative.end, len(p.assignments))
        for p in output
        if len(p.assignments) > 1
    )
    assert shared == [(0, 1, 3), (1, 4, 2), (4, 5, 3)]
    unique = [p for p in output if len(p.assignments) == 1]
    assert unique[0].assignments == (Assignment("c", 1, 4),)
    assert unique[0].coordinates == tuple(branch[1:5])


def test_reverse_direction_and_repeated_visits_do_not_double_count():
    """An opposite-direction pass stays unique; a repeated visit remains a source interval."""
    trajectories = [
        metric("a", [(0, 0), (10, 0), (0, 0), (10, 0)]),
        metric("b", [(0, 0), (10, 0)]),
        metric("c", [(10, 0), (0, 0)]),
    ]
    output = cluster(trajectories)
    assert len(output) == 3
    assert all(len(p.assignments) == 2 for p in output[:2])
    for pathlet in output:
        assert len({a.trajectory_id for a in pathlet.assignments}) == len(pathlet.assignments)
    assert sorted((a.start, a.end) for p in output for a in p.assignments if a.trajectory_id == "a") == [
        (0, 1),
        (1, 2),
        (2, 3),
    ]


def test_failed_prefix_does_not_prune_longer_valid_extension(monkeypatch):
    """An alternating offset makes a two-edge prefix fail but a three-edge prefix pass."""
    trajectories = [
        metric("a", [(0, 0), (10, 0), (20, 0), (30, 0)]),
        metric("b", [(0, 2), (10, 0), (20, 2), (30, 0)]),
    ]
    atoms = []
    for index in range(3):
        a, b = Assignment("a", index, index + 1), Assignment("b", index, index + 1)
        distance = sspd(interval_coordinates(trajectories[0], a), interval_coordinates(trajectories[1], b))
        assert distance <= 1
        atoms.append(ExtendedPathletCandidate(a, (a, b), (index,), distance))
    assert sspd(trajectories[0].coordinates[:3], trajectories[1].coordinates[:3]) > 1
    assert sspd(trajectories[0].coordinates, trajectories[1].coordinates) <= 1
    monkeypatch.setattr("pathlets.extension.generate_overlap_atoms", lambda *args: atoms)
    extended = extend_clusters([], trajectories, [], [], ClusteringConfig(Path("x"), epsilon_m=1))
    assert any(candidate.representative == Assignment("a", 0, 3) for candidate in extended)
    bounded = extend_clusters(
        [], trajectories, [], [], ClusteringConfig(Path("x"), epsilon_m=1, max_extension_steps=2)
    )
    assert all(candidate.representative.end - candidate.representative.start <= 2 for candidate in bounded)


def test_stationary_and_unmatched_portions_survive_length_filter():
    """The minimum shared length never removes a source interval or duplicate point."""
    trajectories = [
        metric("a", [(0, 0), (0, 0), (10, 0)]),
        metric("b", [(0, 0), (10, 0)]),
        metric("c", [(100, 100), (100, 100)]),
    ]
    config = ClusteringConfig(Path("x"), epsilon_m=0, min_pathlet_length_m=100)
    segments = generate_segments(trajectories)
    pairs = find_nearby_pairs(segments, build_spatial_index(segments), config)
    clusters = construct_candidate_clusters(segments, compare_sspd(pairs, segments, 0))
    atoms = generate_overlap_atoms(clusters, segments, pairs, trajectories, config)
    assert len(atoms) == 2
    selected = select_final_pathlets(atoms, trajectories, config)
    validate_coverage(selected, trajectories)
    assert len(selected) == 3
    assert all(len(p.assignments) == 1 for p in selected)
    assert selected[0].coordinates == trajectories[0].coordinates
    assert selected[2].coordinates == ((100, 100), (100, 100))
    assert uncovered_intervals(5, [(1, 3), (2, 4)]) == [(0, 1), (4, 5)]


@pytest.mark.parametrize(("offset", "merges"), [(1, True), (10, False)])
def test_extension_includes_gap_geometry_and_rechecks_sspd(offset, merges):
    """A bounded seed gap is filled with original geometry and accepted only after SSPD."""
    trajectories = [
        metric("a", [(0, 0), (10, 0), (20, 0), (30, 0), (40, 0)]),
        metric("b", [(0, 0), (10, 0), (20, offset), (30, 0), (40, 0)]),
    ]
    config = ClusteringConfig(Path("unused"), epsilon_m=0.3, extension_gap_m=100)
    segments = generate_segments(trajectories)
    pairs = find_nearby_pairs(segments, build_spatial_index(segments), config)
    stars = construct_candidate_clusters(segments, compare_sspd(pairs, segments, config.epsilon_m))
    extended = extend_clusters(stars, trajectories, segments, pairs, config)
    full = [c for c in extended if c.representative.start == 0 and c.representative.end == 4]
    assert bool(full) is merges
    selected = select_final_pathlets(extended, trajectories, config)
    validate_coverage(selected, trajectories)
    if merges:
        assert len(selected) == 1
        assert len(selected[0].assignments) == 2
    else:
        assert any(len(p.assignments) == 1 for p in selected)


def test_no_transitive_final_assignment_and_deterministic_selection():
    """Every assigned path passes SSPD to its chosen representative, with stable tie breaks."""
    trajectories = [
        metric("a", [(0, 0), (10, 0)]),
        metric("b", [(0, 1), (10, 1)]),
        metric("c", [(0, 2), (10, 2)]),
    ]
    first = cluster(trajectories, 1)
    assert first == cluster(trajectories, 1)
    assert len(first) == 1
    assert first[0].representative.trajectory_id == "b"
    assert len(first[0].assignments) == 3
    by_id = {t.trajectory_id: t for t in trajectories}
    for pathlet in first:
        for assignment in pathlet.assignments:
            assert (
                sspd(pathlet.coordinates, interval_coordinates(by_id[assignment.trajectory_id], assignment))
                <= 1
            )


@pytest.mark.parametrize(
    "changes",
    [
        {"epsilon_m": -1},
        {"epsilon_m": float("nan")},
        {"search_radius_m": 399},
        {"max_extension_steps": 0},
        {"plot_sample_size": 0},
        {"direction_cosine_min": 1.1},
        {"debug_steps": frozenset({10})},
        {"max_projection_radius_m": 2_000_000},
    ],
)
def test_config_validation(changes):
    """Incorrect units, unsafe search radii, and invalid extension budgets are rejected."""
    with pytest.raises(ValueError):
        ClusteringConfig(Path("x"), **changes)


def test_explicit_approximate_search_and_existing_model_adapter():
    """Approximation is opt-in, and existing models can enter without CSV or database code."""
    config = ClusteringConfig(Path("x"), search_radius_m=10, approximate_search=True)
    assert config.radius_m == 10
    point = UniformedTrajectoryPoint(9, EPOCH, 56)
    uniformed = UniformedTrajectories(5, VehicleType.CAR, EPOCH, [point, replace(point, longitude=9.1)], 42)
    adapted = from_uniformed("source-id", uniformed)
    assert adapted.trajectory_id == "source-id"
    assert adapted.points == tuple(uniformed.points)
    assert adapted.metadata["database_trajectory_id"] == 42


def test_loader_preserves_string_ids_and_reports_malformed_rows(tmp_path):
    """CSV row parsing retains source IDs instead of optional database IDs."""
    fixture = Path(__file__).parents[1] / "data/trajectories/aalborg_germany.csv"
    trajectories = load_trajectories(fixture)
    assert [t.trajectory_id for t in trajectories] == ["demo", *[f"demo_{i}" for i in range(2, 9)]]
    assert sum(len(t.points) for t in trajectories) == 198
    assert trajectories[0].source_rows[0] == 2
    malformed = tmp_path / "bad.csv"
    malformed.write_text("latitude,longitude\n56,10\n")
    with pytest.raises(ValueError, match="line 1"):
        load_trajectories(malformed)


def test_fractional_interval_retains_original_bends():
    """Extracting an interval never replaces the original route with an endpoint chord."""
    trajectory = metric("a", [(0, 0), (10, 0), (10, 10), (20, 10)])
    coordinates = interval_coordinates(trajectory, Assignment("a", 0.5, 2.5))
    assert coordinates == ((5, 0), (10, 0), (10, 10), (15, 10))
    assert length(coordinates) == 20
    assert length(coordinates) > hypot(15 - 5, 10)
