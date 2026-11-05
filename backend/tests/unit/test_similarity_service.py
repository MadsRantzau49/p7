import math
import random
from collections import Counter
from datetime import UTC, datetime

import pytest
from helpers.similarity_steps.greedy_clustering import _BackboneIndex
from models.similarity import ProjectedTrajectory, Projection
from models.subtrajectory import Subtrajectory
from models.uniformed_trajectories import UniformedTrajectoryPoint
from services.similarity_service import SimilarityService
from shapely.geometry import LineString, Point
from shapely.ops import substring


def projected(trajectory_id, coordinates):
    """Build a trajectory in metres for geometry tests independent of projection."""
    return ProjectedTrajectory(trajectory_id, [Projection(x, y) for x, y in coordinates])


def cluster(trajectories, epsilon):
    """Run the projected part of the pipeline and retain its coverage information."""
    service = SimilarityService()
    return service.extend_pathlets(trajectories, epsilon)


def assert_coverage_and_distance(pathlets, trajectories, epsilon):
    """Check exact coverage and geometry against an independent GEOS distance oracle."""
    expected = Counter(
        (section_index, segment_index)
        for section_index, trajectory in enumerate(trajectories)
        for segment_index in range(len(trajectory.projected_points) - 1)
    )
    actual = Counter()
    for pathlet in pathlets:
        assert pathlet.count == len({section.trajectory_id for section in pathlet.sections})
        representative = pathlet.representative
        coordinates = [(point.x, point.y) for point in representative.points]
        representative_line = LineString(coordinates) if len(coordinates) > 1 else Point(coordinates[0])
        assert representative in pathlet.sections
        for section in pathlet.sections:
            original = trajectories[section.section_index]
            assert section.trajectory_id == original.trajectory_id
            assert section.points == original.projected_points[section.start_index : section.end_index + 1]
            actual.update(
                (section.section_index, index) for index in range(section.start_index, section.end_index)
            )
            coordinates = [(point.x, point.y) for point in section.points]
            member_line = LineString(coordinates) if len(coordinates) > 1 else Point(coordinates[0])
            reference_interval = (
                substring(representative_line, section.representative_start_m, section.representative_end_m)
                if representative_line.length > 0 else representative_line
            )
            assert reference_interval.hausdorff_distance(member_line) <= epsilon + 1e-7
        for interval in pathlet.support:
            midpoint = (interval.start_m + interval.end_m) / 2
            ids = {
                section.trajectory_id for section in pathlet.sections
                if section.representative_start_m <= midpoint <= section.representative_end_m
            }
            assert interval.count == len(ids)
    assert actual == expected


@pytest.mark.parametrize("reverse", [False, True])
def test_parallel_sections_stitch_in_either_direction(reverse):
    """Full supporting sections join even when one trajectory travels backwards."""
    coordinates = [(0, 0), (10, 0), (20, 0), (30, 0)]
    other = [(x, 0.5) for x, _ in coordinates]
    trajectories = [projected(1, coordinates), projected(2, other[::-1] if reverse else other)]

    pathlets = cluster(trajectories, 1)

    assert len(pathlets) == 1
    assert pathlets[0].count == 2
    assert pathlets[0].representative.points == trajectories[0].projected_points
    assert_coverage_and_distance(pathlets, trajectories, 1)


@pytest.mark.parametrize(
    ("other", "epsilon", "shared"),
    [
        ([(0, 5), (10, 5)], 5, True),
        ([(0, 5), (10, 5)], math.nextafter(5, 0), False),
        ([(3, 4), (13, 4)], 5, True),
        ([(10, 0), (0, 0)], 0, True),
        ([(0, 0), (10, 4)], 2, False),  # Averages can pass; the far endpoint must fail.
        ([(5, -5), (5, 5)], 1, False),  # A crossing alone is not shared geometry.
    ],
)
def test_epsilon_bounds_corresponding_endpoints(other, epsilon, shared):
    """Use inclusive metre bounds rather than average distance or box overlap."""
    trajectories = [projected(1, [(0, 0), (10, 0)]), projected(2, other)]
    pathlets = cluster(trajectories, epsilon)

    assert any(pathlet.count == 2 for pathlet in pathlets) == shared
    assert_coverage_and_distance(pathlets, trajectories, epsilon)


def test_matches_are_not_transitive():
    """Nearby intermediate trajectories cannot join sections outside the representative's epsilon."""
    trajectories = [projected(index, [(0, index), (10, index)]) for index in range(3)]
    pathlets = cluster(trajectories, 1.1)

    assert sorted(pathlet.count for pathlet in pathlets) == [1, 2]
    assert_coverage_and_distance(pathlets, trajectories, 1.1)


def test_pathlet_continues_where_partial_support_ends():
    """A supporter leaving closes its interval rather than splitting the backbone."""
    trajectories = [
        projected(1, [(0, 0), (10, 0), (20, 0), (30, 0)]),
        projected(2, [(0, 0), (10, 0), (20, 0)]),
    ]
    pathlets = cluster(trajectories, 0)

    assert len(pathlets) == 1
    assert pathlets[0].count == 2
    assert len(pathlets[0].representative.points) == 4
    assert [(part.start_m, part.end_m, part.count) for part in pathlets[0].support] == [
        (0, 20, 2), (20, 30, 1),
    ]
    assert_coverage_and_distance(pathlets, trajectories, 0)


def test_repeated_source_ids_keep_separate_coverage_and_distinct_counts():
    """Multiple sections of one source neither overwrite coverage nor inflate support."""
    trajectories = [
        projected(7, [(0, 0), (10, 0), (20, 0)]),
        projected(7, [(0, 0.5), (10, 0.5), (20, 0.5)]),
        projected(8, [(0, 1), (10, 1), (20, 1)]),
        projected(7, [(100, 100), (110, 100)]),
    ]
    pathlets = cluster(trajectories, 1)

    assert sorted(pathlet.count for pathlet in pathlets) == [1, 2]
    assert_coverage_and_distance(pathlets, trajectories, 1)


def test_zero_length_segments_are_assigned_even_with_zero_epsilon():
    """Stationary observations remain represented without a positive-distance gain."""
    trajectories = [
        projected(1, [(0, 0), (0, 0), (10, 0)]),
        projected(2, [(0, 0), (0, 0)]),
    ]
    pathlets = cluster(trajectories, 0)

    assert len(pathlets) == 1
    assert pathlets[0].count == 2
    assert_coverage_and_distance(pathlets, trajectories, 0)


def test_single_point_section_is_preserved():
    """An input without any segments still produces its original point."""
    trajectory = projected(1, [(3, 4)])
    [pathlet] = cluster([trajectory], 0)

    assert pathlet.count == 1
    assert pathlet.representative.points == trajectory.projected_points
    assert pathlet.sections == [pathlet.representative]


@pytest.mark.parametrize("epsilon", [0, 0.5, 5, 50])
def test_mixed_sampling_loops_and_reversed_sections_keep_all_geometry(epsilon, monkeypatch):
    """Exercise disjoint runs, many-to-one matches and greedy overlaps with a geometry oracle."""
    random_source = random.Random(147)
    trajectories = []
    for index in range(24):
        offset = random_source.choice([0, 0.5, 3, 10])
        coordinates = [(x, y + offset) for x, y in [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]]
        if index % 3 == 0:
            coordinates += coordinates[1:]
        if index % 4 == 0:
            coordinates = [coordinates[0], coordinates[0], *coordinates[1:]]
        if index % 5 == 0:
            coordinates = coordinates[::2]
        if random_source.choice([False, True]):
            coordinates.reverse()
        trajectories.append(projected(index // 2, coordinates))

    first = cluster(trajectories, epsilon)
    second = cluster(trajectories, epsilon)

    assert first == second
    assert_coverage_and_distance(first, trajectories, epsilon)

    # Bypass the grid: spatial filtering must retain every valid seed.
    original_seeds = _BackboneIndex.seeds

    def exhaustive_seeds(self, point):
        exhaustive = _BackboneIndex(self.epsilon, self.cell_size)
        by_identity = {id(item): item for cell in self.cells.values() for item in cell}
        by_identity.update((id(item), item) for item in self.long_edges)
        exhaustive.long_edges = sorted(by_identity.values(), key=lambda item: (item.backbone, item.edge))
        return original_seeds(exhaustive, point)

    monkeypatch.setattr(_BackboneIndex, "seeds", exhaustive_seeds)
    assert cluster(trajectories, epsilon) == first


def test_different_sampling_extends_through_bends():
    """Many short segments and fewer long segments can form the same extended pathlet."""
    trajectories = [
        projected(1, [(0, 0), (30, 0), (30, 30)]),
        projected(2, [(0, 0), (10, 0), (20, 0), (30, 0), (30, 10), (30, 20), (30, 30)]),
    ]
    pathlets = cluster(trajectories, 0)

    assert len(pathlets) == 1
    assert pathlets[0].count == 2
    assert pathlets[0].support[0].count == 2
    assert_coverage_and_distance(pathlets, trajectories, 0)


def test_partial_support_can_handoff_without_splitting():
    """Joining and leaving supporters produce local counts along one long representative."""
    trajectories = [
        projected(1, [(0, 0), (20, 0), (40, 0), (60, 0)]),
        projected(2, [(0, 0), (20, 0), (40, 0)]),
        projected(3, [(60, 0), (40, 0), (20, 0)]),
        projected(3, [(20, 0), (40, 0)]),  # Same source must count once in overlapping intervals.
    ]
    pathlets = cluster(trajectories, 0)

    assert len(pathlets) == 1
    assert pathlets[0].count == 3
    assert [(part.start_m, part.end_m, part.count) for part in pathlets[0].support] == [
        (0, 20, 2), (20, 40, 3), (40, 60, 2),
    ]
    assert any(section.reversed for section in pathlets[0].sections)
    assert_coverage_and_distance(pathlets, trajectories, 0)


def test_reference_corners_are_checked_inside_a_long_source_segment():
    """Matching endpoints cannot hide a shortcut across a distant bend."""
    trajectories = [
        projected(1, [(0, 0), (10, 0), (10, 10)]),
        projected(2, [(0, 0), (10, 10)]),
    ]
    pathlets = cluster(trajectories, 1)

    assert len(pathlets) == 2
    assert_coverage_and_distance(pathlets, trajectories, 1)


def test_long_diagonal_reference_uses_sparse_index_without_losing_matches():
    """A huge expanded box must not allocate a giant grid or miss an interior match."""
    trajectories = [
        projected(1, [(0, 0), (20000, 20000)]),
        projected(2, [(5000 + index, 5000 + index) for index in range(11)]),
    ]
    pathlets = cluster(trajectories, 1)

    assert len(pathlets) == 1
    assert pathlets[0].count == 2
    assert len(pathlets[0].support) == 3
    assert_coverage_and_distance(pathlets, trajectories, 1)


@pytest.mark.parametrize("epsilon", [-1, math.nan, math.inf, -math.inf])
def test_invalid_epsilon_is_rejected(epsilon):
    """Reject invalid tolerances before constructing spatial bounds."""
    with pytest.raises(ValueError, match="epsilon must be finite and non-negative"):
        SimilarityService().find_similar_trajectories([], epsilon)


@pytest.mark.parametrize("capacity", [0, 1])
def test_invalid_tree_capacity_is_rejected(capacity):
    """A tree fanout of one must not enter a non-shrinking build loop."""
    with pytest.raises(ValueError, match="r_tree_max_entries must be at least 2"):
        SimilarityService().find_similar_trajectories([], 1, capacity)


def test_absent_and_empty_inputs():
    """Keep absent input semantics and accept an empty query result."""
    service = SimilarityService()
    assert service.find_similar_trajectories(None, 1) is None
    assert service.find_similar_trajectories([], 1) == []


def test_public_pipeline_roundtrips_gps_and_can_be_reused():
    """Exercise projection, clustering and inverse projection together, across requests."""
    coordinates = [(10.20, 56.15), (10.201, 56.151), (10.202, 56.152)]
    now = datetime(2026, 1, 1, tzinfo=UTC)
    sections = [
        Subtrajectory(
            index,
            index,
            now,
            now,
            [UniformedTrajectoryPoint(lon, now, lat) for lon, lat in route],
        )
        for index, route in enumerate([coordinates, coordinates[::-1]])
    ]
    service = SimilarityService()
    first = service.find_similar_trajectories(sections, 0)
    second = service.find_similar_trajectories(sections[:1], 0)

    assert first is not None and second is not None
    assert len(first) == len(second) == 1
    assert first[0].count == 2
    assert second[0].count == 1
    assert len(first[0].support) == 1
    assert first[0].support[0].count == 2
    assert first[0].support[0].end_m > 0
    for point, (longitude, latitude) in zip(first[0].points, coordinates, strict=True):
        assert point.longitude == pytest.approx(longitude, abs=1e-9)
        assert point.latitude == pytest.approx(latitude, abs=1e-9)
