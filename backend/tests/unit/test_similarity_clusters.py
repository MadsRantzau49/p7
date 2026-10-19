from models.similarity import Coordinate, MatchingSegmentPair, TrajectorySegments
from services.similarity_service import SimilarityService


def make_segment(trajectory_id, segment_index=0, y=0):
    """Build a horizontal segment with its original trajectory ID and index."""
    return TrajectorySegments(
        trajectory_id=trajectory_id,
        segment_index=segment_index,
        start=Coordinate(0, y),
        end=Coordinate(1, y),
    )


def test_segments_without_matches_form_singleton_clusters():
    """Every segment is a representative, including segments without matches."""
    service = SimilarityService()
    first = make_segment(1)
    second = make_segment(2)

    clusters = service.construct_candidate_clusters([first, second], [])

    assert len(clusters) == 2
    assert clusters[0].representative is first
    assert clusters[0].segments == [first]
    assert clusters[0].trajectories_included == [1]
    assert clusters[0].trajectory_count == 1
    assert clusters[1].representative is second
    assert clusters[1].segments == [second]
    assert clusters[1].trajectories_included == [2]
    assert clusters[1].trajectory_count == 1


def test_direct_matches_are_added_in_both_directions():
    """Both segments in a matching pair receive the other as a cluster member."""
    service = SimilarityService()
    first = make_segment(1)
    second = make_segment(2)
    isolated = make_segment(3)
    pairs = [MatchingSegmentPair(first, second)]

    clusters = service.construct_candidate_clusters([first, second, isolated], pairs)

    assert len(clusters) == 3
    assert clusters[0].segments == [first, second]
    assert clusters[0].trajectories_included == [1, 2]
    assert clusters[0].trajectory_count == 2
    assert clusters[1].segments == [second, first]
    assert clusters[1].trajectories_included == [1, 2]
    assert clusters[1].trajectory_count == 2
    assert clusters[2].segments == [isolated]
    assert clusters[2].trajectories_included == [3]
    assert clusters[2].trajectory_count == 1


def test_candidate_clusters_do_not_include_transitive_matches():
    """A-B and B-C matches produce overlapping clusters without adding A-C."""
    service = SimilarityService()
    first = make_segment(1, y=0)
    middle = make_segment(2, y=0.4)
    last = make_segment(3, y=0.8)
    segments = [first, middle, last]
    root = service.build_rtree(segments, epsilon=0.5, max_entries=2)
    pairs = service.find_matching_segment_pairs(segments, root, epsilon=0.5)

    clusters = service.construct_candidate_clusters(segments, pairs)

    assert len(clusters) == 3
    assert clusters[0].representative is first
    assert clusters[0].segments == [first, middle]
    assert clusters[0].trajectories_included == [1, 2]
    assert clusters[0].trajectory_count == 2
    assert clusters[1].representative is middle
    assert len(clusters[1].segments) == 3
    assert first in clusters[1].segments
    assert last in clusters[1].segments
    assert clusters[1].trajectory_count == 3
    assert clusters[1].trajectories_included == [1, 2, 3]
    assert clusters[2].representative is last
    assert clusters[2].segments == [last, middle]
    assert clusters[2].trajectories_included == [2, 3]
    assert clusters[2].trajectory_count == 2


def test_multiple_segments_from_one_trajectory_count_once():
    """Keep every matched segment while counting distinct trajectory IDs."""
    service = SimilarityService()
    representative = make_segment(1)
    first_match = make_segment(2, segment_index=0)
    second_match = make_segment(2, segment_index=1)
    segments = [representative, first_match, second_match]
    pairs = [
        MatchingSegmentPair(representative, first_match),
        MatchingSegmentPair(representative, second_match),
    ]

    clusters = service.construct_candidate_clusters(segments, pairs)

    assert len(clusters) == 3
    assert clusters[0].segments == [representative, first_match, second_match]
    assert clusters[0].trajectories_included == [1, 2]
    assert clusters[0].trajectory_count == 2
    assert clusters[1].representative is first_match
    assert clusters[1].segments == [first_match, representative]
    assert clusters[1].trajectories_included == [1, 2]
    assert clusters[1].trajectory_count == 2
    assert clusters[2].representative is second_match
    assert clusters[2].segments == [second_match, representative]
    assert clusters[2].trajectories_included == [1, 2]
    assert clusters[2].trajectory_count == 2


def test_duplicate_pairs_do_not_duplicate_cluster_members():
    """Treat repeated and reversed pairs as the same direct match."""
    service = SimilarityService()
    first = make_segment(1)
    second = make_segment(2)
    pairs = [
        MatchingSegmentPair(first, second),
        MatchingSegmentPair(second, first),
        MatchingSegmentPair(first, second),
    ]

    clusters = service.construct_candidate_clusters([first, second], pairs)

    assert clusters[0].segments == [first, second]
    assert clusters[0].trajectories_included == [1, 2]
    assert clusters[0].trajectory_count == 2
    assert clusters[1].segments == [second, first]
    assert clusters[1].trajectories_included == [1, 2]
    assert clusters[1].trajectory_count == 2


def test_no_segments_produce_no_candidate_clusters():
    """An empty segment collection has no representatives."""
    assert SimilarityService().construct_candidate_clusters([], []) == []
