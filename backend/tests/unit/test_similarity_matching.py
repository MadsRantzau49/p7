import math

import pytest
from models.similarity import Coordinate, TrajectorySegments
from services.similarity_service import SimilarityService


def make_segment(trajectory_id, start, end, segment_index=0):
    """Build an original segment from two (x, y) pairs in meters."""
    return TrajectorySegments(
        trajectory_id=trajectory_id,
        segment_index=segment_index,
        start=Coordinate(*start),
        end=Coordinate(*end),
    )


def test_point_distance_uses_the_segment_and_its_endpoints():
    """Use perpendicular distance inside the segment and endpoint distance outside."""
    service = SimilarityService()
    segment = make_segment(1, (0, 0), (4, 0))

    assert service.point_to_segment_distance(Coordinate(2, 3), segment) == 3
    assert service.point_to_segment_distance(Coordinate(-3, 4), segment) == 5
    assert service.point_to_segment_distance(Coordinate(7, 4), segment) == 5


def test_point_distance_to_vertical_and_diagonal_segments():
    """Measure distances independently of segment orientation."""
    service = SimilarityService()
    vertical = make_segment(1, (0, 0), (0, 4))
    diagonal = make_segment(2, (0, 0), (2, 2))

    assert service.point_to_segment_distance(Coordinate(3, 2), vertical) == 3
    assert service.point_to_segment_distance(Coordinate(2, 0), diagonal) == pytest.approx(math.sqrt(2))


def test_point_distance_to_zero_length_segment():
    """Treat repeated endpoints as a point rather than dividing by zero."""
    service = SimilarityService()
    segment = make_segment(1, (1, 1), (1, 1))

    assert service.point_to_segment_distance(Coordinate(4, 5), segment) == 5


def test_sspd_averages_both_directions():
    """A contained segment has zero directed distance, but its reverse does not."""
    service = SimilarityService()
    long_segment = make_segment(1, (0, 0), (4, 0))
    short_segment = make_segment(2, (1, 0), (2, 0))

    # Long to short: (1 + 2) / 2 = 1.5. Short to long: 0.
    assert service.sspd(long_segment, short_segment) == 0.75
    assert service.sspd(short_segment, long_segment) == 0.75


def test_parallel_segments_match_at_the_distance_threshold():
    """Include a pair when its SSPD is exactly epsilon."""
    service = SimilarityService()
    segments = [make_segment(1, (0, 0), (4, 0)), make_segment(2, (0, 0.5), (4, 0.5))]
    root = service.build_rtree(segments, epsilon=0.5, max_entries=2)

    matches = service.find_matching_segment_pairs(segments, root, epsilon=0.5)

    assert len(matches) == 1
    assert matches[0].segment_a is segments[0]
    assert matches[0].segment_b is segments[1]


def test_box_intersection_does_not_guarantee_a_match():
    """Reject crossing segments whose boxes intersect but whose SSPD is too large."""
    service = SimilarityService()
    horizontal = make_segment(1, (-2, 0), (2, 0))
    vertical = make_segment(2, (0, -2), (0, 2))
    segments = [horizontal, vertical]
    root = service.build_rtree(segments, epsilon=0.5, max_entries=2)

    assert vertical in service.query_rtree(root, service.bounding_box(horizontal))
    assert service.sspd(horizontal, vertical) == 2
    assert service.find_matching_segment_pairs(segments, root, epsilon=0.5) == []


def test_candidate_queries_use_original_boxes(monkeypatch):
    """Skip SSPD when only expanding the query box as well would produce a hit."""
    service = SimilarityService()
    segments = [make_segment(1, (0, 0), (4, 0)), make_segment(2, (0, 1.5), (4, 1.5))]
    root = service.build_rtree(segments, epsilon=1, max_entries=2)

    def unexpected_sspd(segment_a, segment_b):
        pytest.fail("SSPD should only run for R-tree candidates")

    monkeypatch.setattr(service, "sspd", unexpected_sspd)

    assert service.find_matching_segment_pairs(segments, root, epsilon=1) == []


def test_segments_from_the_same_trajectory_do_not_match():
    """Exclude same-trajectory pairs even when their geometry is identical."""
    service = SimilarityService()
    segments = [
        make_segment(1, (0, 0), (4, 0), segment_index=0),
        make_segment(1, (0, 0), (4, 0), segment_index=1),
    ]
    root = service.build_rtree(segments, epsilon=1, max_entries=2)

    assert service.find_matching_segment_pairs(segments, root, epsilon=1) == []


def test_each_pair_is_kept_once_with_original_ids_and_indices():
    """Order pairs by trajectory ID even when input segments are in reverse order."""
    service = SimilarityService()
    higher_id = make_segment(7, (0, 0.2), (4, 0.2), segment_index=9)
    lower_id = make_segment(2, (0, 0), (4, 0), segment_index=4)
    segments = [higher_id, lower_id]
    root = service.build_rtree(segments, epsilon=0.5, max_entries=2)

    matches = service.find_matching_segment_pairs(segments, root, epsilon=0.5)

    assert len(matches) == 1
    assert matches[0].segment_a is lower_id
    assert matches[0].segment_b is higher_id
    assert matches[0].segment_a.segment_index == 4
    assert matches[0].segment_b.segment_index == 9


def test_distinct_segment_pairs_from_the_same_two_trajectories_are_kept():
    """Keep both matching segments, including when the R-tree has multiple leaves."""
    service = SimilarityService()
    segments = [
        make_segment(1, (0, 0), (4, 0), segment_index=0),
        make_segment(1, (4, 0), (0, 0), segment_index=1),
        make_segment(2, (0, 0.2), (4, 0.2), segment_index=0),
    ]
    root = service.build_rtree(segments, epsilon=0.5, max_entries=2)

    matches = service.find_matching_segment_pairs(segments, root, epsilon=0.5)

    assert len(matches) == 2
    assert {(pair.segment_a.segment_index, pair.segment_b.segment_index) for pair in matches} == {
        (0, 0), (1, 0),
    }


def test_identical_reversed_segments_match_at_zero_epsilon():
    """SSPD compares geometry without imposing an additional direction rule."""
    service = SimilarityService()
    segments = [make_segment(1, (0, 0), (4, 0)), make_segment(2, (4, 0), (0, 0))]
    root = service.build_rtree(segments, epsilon=0, max_entries=2)

    matches = service.find_matching_segment_pairs(segments, root, epsilon=0)

    assert len(matches) == 1
    assert matches[0].segment_a is segments[0]
    assert matches[0].segment_b is segments[1]


def test_no_segments_produce_no_matching_pairs():
    """An empty tree and segment collection have no matches."""
    assert SimilarityService().find_matching_segment_pairs([], None, epsilon=1) == []


def test_matching_pairs_reject_negative_epsilon():
    """A distance threshold cannot be negative."""
    with pytest.raises(ValueError, match="epsilon must be non-negative"):
        SimilarityService().find_matching_segment_pairs([], None, epsilon=-1)
