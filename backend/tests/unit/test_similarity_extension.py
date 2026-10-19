import pytest
from models.similarity import CandidateCluster, Coordinate, ProjectedTrajectory, TrajectorySection
from services.similarity_service import SimilarityService


def make_trajectory(trajectory_id, points):
    """Build a projected trajectory from (x, y) pairs."""
    return ProjectedTrajectory(
        trajectory_id=trajectory_id,
        projected_points=[Coordinate(x, y) for x, y in points],
    )


def make_cluster(segments):
    """Use the first segment as representative and the others as direct matches."""
    trajectory_ids = {segment.trajectory_id for segment in segments}
    return CandidateCluster(
        representative=segments[0],
        segments=segments,
        trajectories_included=list(trajectory_ids),
        trajectory_count=len(trajectory_ids),
    )


def test_path_sspd_uses_interior_points_and_distance_to_the_polyline():
    """Include the bend's distance and project onto edges of the other path."""
    service = SimilarityService()
    bent = TrajectorySection(1, 0, 2, [Coordinate(0, 0), Coordinate(1, 1), Coordinate(2, 0)])
    straight = TrajectorySection(2, 0, 2, [Coordinate(0, 0), Coordinate(1, 0), Coordinate(2, 0)])

    # Directed distances: 1/3 and (1/sqrt(2))/3, averaged together.
    assert service.path_sspd(bent, straight) == pytest.approx(0.284518, abs=0.000001)
    assert service.path_sspd(straight, bent) == pytest.approx(0.284518, abs=0.000001)


def test_extension_keeps_the_short_candidate_when_a_trajectory_turns_away():
    """The example keeps support three for the short path and two for the longer path."""
    service = SimilarityService()
    trajectories = [
        make_trajectory(1, [(0, 0), (1, 0), (2, 0)]),
        make_trajectory(2, [(0, 0.2), (1, 0.2), (2, 0.2)]),
        make_trajectory(3, [(0, 0.1), (1, 0.1), (2, 2)]),
    ]
    segments = service.generate_segments(trajectories)
    cluster = make_cluster([segments[0], segments[2], segments[4]])

    candidates = service.extend_candidate_clusters([cluster], trajectories, epsilon=0.5)

    assert len(candidates) == 2
    short, long = candidates
    assert short.representative.points == trajectories[0].projected_points[:2]
    assert short.trajectory_count == 3
    assert set(short.trajectories_included) == {1, 2, 3}
    assert [section.end_index for section in short.sections] == [1, 1, 1]
    assert long.representative.points == trajectories[0].projected_points
    assert long.trajectory_count == 2
    assert set(long.trajectories_included) == {1, 2}
    assert [section.trajectory_id for section in long.sections] == [1, 2]
    assert [section.end_index for section in long.sections] == [2, 2]

    turned_path = TrajectorySection(3, 0, 2, trajectories[2].projected_points)
    assert service.path_sspd(long.representative, turned_path) == pytest.approx(0.56, abs=0.01)


def test_a_failed_match_does_not_rejoin_the_group_later():
    """Once an extension fails, retain its short match and continue the surviving paths."""
    service = SimilarityService()
    trajectories = [
        make_trajectory(1, [(0, 0), (1, 0), (2, 0), (3, 0)]),
        make_trajectory(2, [(0, 0.1), (1, 0.1), (2, 2), (3, 0.1)]),
        make_trajectory(3, [(0, 0.2), (1, 0.2), (2, 0.2), (3, 0.2)]),
    ]
    segments = service.generate_segments(trajectories)
    cluster = make_cluster([segments[0], segments[3], segments[6]])

    candidates = service.extend_candidate_clusters([cluster], trajectories, epsilon=0.5)

    assert len(candidates) == 3
    assert candidates[0].trajectory_count == 3
    assert set(candidates[1].trajectories_included) == {1, 3}
    assert set(candidates[2].trajectories_included) == {1, 3}
    # The full paths would match again, but trajectory 2 already failed earlier.
    full_second_path = TrajectorySection(2, 0, 3, trajectories[1].projected_points)
    assert service.path_sspd(candidates[2].representative, full_second_path) < 0.5


def test_a_matching_trajectory_can_end_before_the_representative():
    """Keep ended trajectories in shorter candidates while other matches extend."""
    service = SimilarityService()
    trajectories = [
        make_trajectory(1, [(0, 0), (1, 0), (2, 0), (3, 0)]),
        make_trajectory(2, [(0, 0.1), (1, 0.1)]),
        make_trajectory(3, [(0, 0.2), (1, 0.2), (2, 0.2)]),
    ]
    segments = service.generate_segments(trajectories)
    cluster = make_cluster([segments[0], segments[3], segments[4]])

    candidates = service.extend_candidate_clusters([cluster], trajectories, epsilon=0.5)

    assert len(candidates) == 2
    assert set(candidates[0].trajectories_included) == {1, 2, 3}
    assert set(candidates[1].trajectories_included) == {1, 3}
    assert candidates[1].representative.end_index == 2
    assert candidates[1].sections[1].end_index == 2


def test_extension_stops_when_the_representative_ends():
    """Do not extend other paths beyond the representative's last point."""
    service = SimilarityService()
    trajectories = [
        make_trajectory(1, [(0, 0), (1, 0)]),
        make_trajectory(2, [(0, 0.2), (1, 0.2), (2, 0.2)]),
    ]
    segments = service.generate_segments(trajectories)
    cluster = make_cluster([segments[0], segments[1]])

    candidates = service.extend_candidate_clusters([cluster], trajectories, epsilon=0.5)

    assert len(candidates) == 1
    assert candidates[0].representative.end_index == 1
    assert candidates[0].trajectory_count == 2
    assert candidates[0].sections[1].end_index == 1


def test_extension_stops_when_all_other_matches_fail():
    """Preserve the shorter candidate if nobody matches the longer representative."""
    service = SimilarityService()
    trajectories = [
        make_trajectory(1, [(0, 0), (1, 0), (2, 0)]),
        make_trajectory(2, [(0, 0.1), (1, 0.1), (2, 10)]),
    ]
    segments = service.generate_segments(trajectories)
    cluster = make_cluster([segments[0], segments[2]])

    candidates = service.extend_candidate_clusters([cluster], trajectories, epsilon=0.5)

    assert len(candidates) == 1
    assert candidates[0].representative.end_index == 1
    assert candidates[0].trajectory_count == 2


def test_extension_preserves_start_indexes_and_does_not_repeat_shared_endpoints():
    """Start at an interior segment and append exactly one point per extension."""
    service = SimilarityService()
    trajectories = [
        make_trajectory(1, [(0, 0), (1, 0), (2, 0), (3, 0)]),
        make_trajectory(2, [(0, 0.2), (1, 0.2), (2, 0.2), (3, 0.2)]),
    ]
    segments = service.generate_segments(trajectories)
    cluster = make_cluster([segments[1], segments[4]])

    candidates = service.extend_candidate_clusters([cluster], trajectories, epsilon=0.5)

    assert len(candidates) == 2
    short, long = candidates
    assert short.representative.points == trajectories[0].projected_points[1:3]
    assert short.representative.start_index == 1
    assert short.representative.end_index == 2
    assert long.representative.points == trajectories[0].projected_points[1:4]
    assert long.representative.start_index == 1
    assert long.representative.end_index == 3
    assert long.sections[1].points == trajectories[1].projected_points[1:4]
    assert long.sections[1].start_index == 1
    assert long.sections[1].end_index == 3


def test_multiple_matching_sections_from_one_trajectory_count_once():
    """Preserve alternative section alignments without inflating trajectory support."""
    service = SimilarityService()
    trajectories = [
        make_trajectory(1, [(0, 0), (1, 0), (2, 0)]),
        make_trajectory(2, [(0, 0.1), (1, 0.1), (2, 0.1), (3, 0.1)]),
    ]
    segments = service.generate_segments(trajectories)
    cluster = make_cluster([segments[0], segments[2], segments[3]])

    candidates = service.extend_candidate_clusters([cluster], trajectories, epsilon=1)

    assert len(candidates) == 2
    assert candidates[0].trajectory_count == 2
    assert candidates[1].trajectory_count == 2
    assert set(candidates[1].trajectories_included) == {1, 2}
    assert len(candidates[1].sections) == 3
    assert candidates[1].sections[1].start_index == 0
    assert candidates[1].sections[1].end_index == 2
    assert candidates[1].sections[2].start_index == 1
    assert candidates[1].sections[2].end_index == 3


def test_singleton_clusters_are_preserved():
    """Unmatched original segments remain candidates with support one."""
    service = SimilarityService()
    trajectory = make_trajectory(1, [(0, 0), (1, 0), (2, 0)])
    segments = service.generate_segments([trajectory])
    clusters = service.construct_candidate_clusters(segments, [])

    candidates = service.extend_candidate_clusters(clusters, [trajectory], epsilon=0.5)

    assert len(candidates) == 2
    assert candidates[0].representative.points == trajectory.projected_points[:2]
    assert candidates[1].representative.points == trajectory.projected_points[1:]
    assert candidates[0].trajectory_count == 1
    assert candidates[1].trajectory_count == 1
    assert candidates[0].trajectories_included == [1]
    assert candidates[1].trajectories_included == [1]


def test_no_clusters_produce_no_extended_candidates():
    """An empty cluster collection has nothing to extend."""
    assert SimilarityService().extend_candidate_clusters([], [], epsilon=0.5) == []
