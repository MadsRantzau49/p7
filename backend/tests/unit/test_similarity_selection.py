from models.similarity import Coordinate, ExtendedPathletCandidate, ProjectedTrajectory, TrajectorySection
from services.similarity_service import SimilarityService


def make_trajectory(trajectory_id, points):
    """Build a projected trajectory from (x, y) pairs."""
    return ProjectedTrajectory(trajectory_id, [Coordinate(x, y) for x, y in points])


def make_section(trajectory, start_index, end_index):
    """Select a section using inclusive original point indexes."""
    return TrajectorySection(
        trajectory_id=trajectory.trajectory_id,
        start_index=start_index,
        end_index=end_index,
        points=trajectory.projected_points[start_index:end_index + 1],
    )


def make_candidate(sections):
    """Use the first assigned section as the representative path."""
    trajectory_ids = {section.trajectory_id for section in sections}
    return ExtendedPathletCandidate(
        representative=sections[0],
        sections=sections,
        trajectories_included=list(trajectory_ids),
        trajectory_count=len(trajectory_ids),
    )


def test_long_candidate_is_selected_before_the_remaining_short_section():
    """The example selects four new meters first, then one meter from trajectory 3."""
    service = SimilarityService()
    first = make_trajectory(1, [(0, 0), (1, 0), (2, 0)])
    second = make_trajectory(2, [(0, 0.2), (1, 0.2), (2, 0.2)])
    third = make_trajectory(3, [(0, 0.1), (1, 0.1)])
    short = make_candidate([
        make_section(first, 0, 1), make_section(second, 0, 1), make_section(third, 0, 1),
    ])
    long = make_candidate([make_section(first, 0, 2), make_section(second, 0, 2)])

    pathlets = service.select_final_pathlets([short, long], [first, second, third])

    assert len(pathlets) == 2
    assert pathlets[0].representative is long.representative
    assert pathlets[0].count == 2
    assert set(pathlets[0].trajectories_included) == {1, 2}
    assert pathlets[1].representative is short.representative
    assert pathlets[1].count == 1
    assert pathlets[1].trajectories_included == [3]
    assert pathlets[1].sections == [make_section(third, 0, 1)]
    assert [pathlet.pathlet_id for pathlet in pathlets] == [1, 2]
    assert short.trajectory_count == 3
    assert len(short.sections) == 3


def test_new_coverage_uses_euclidean_length_instead_of_segment_or_trajectory_counts():
    """One ten-meter diagonal contributes more than three two-meter paths."""
    service = SimilarityService()
    diagonal = make_trajectory(1, [(0, 0), (6, 8)])
    second = make_trajectory(2, [(0, 0), (2, 0)])
    third = make_trajectory(3, [(0, 0.1), (2, 0.1)])
    fourth = make_trajectory(4, [(0, 0.2), (2, 0.2)])
    group = make_candidate([
        make_section(second, 0, 1), make_section(third, 0, 1), make_section(fourth, 0, 1),
    ])
    single = make_candidate([make_section(diagonal, 0, 1)])

    pathlets = service.select_final_pathlets([group, single], [diagonal, second, third, fourth])

    assert len(pathlets) == 2
    assert pathlets[0].representative is single.representative
    assert pathlets[0].count == 1
    assert pathlets[1].representative is group.representative
    assert pathlets[1].count == 3


def test_coverage_and_support_are_recalculated_after_each_selection():
    """A seven-meter candidate falls below an independent four-meter candidate after overlap removal."""
    service = SimilarityService()
    first = make_trajectory(1, [(0, 0), (4, 0)])
    second = make_trajectory(2, [(0, 0.1), (4, 0.1)])
    third = make_trajectory(3, [(0, 0.2), (3, 0.2)])
    fourth = make_trajectory(4, [(0, 1), (4, 1)])
    eight_meters = make_candidate([make_section(first, 0, 1), make_section(second, 0, 1)])
    seven_meters = make_candidate([make_section(first, 0, 1), make_section(third, 0, 1)])
    four_meters = make_candidate([make_section(fourth, 0, 1)])

    pathlets = service.select_final_pathlets(
        [eight_meters, seven_meters, four_meters], [first, second, third, fourth]
    )

    assert len(pathlets) == 3
    assert pathlets[0].representative is eight_meters.representative
    assert pathlets[1].representative is four_meters.representative
    assert pathlets[2].representative is seven_meters.representative
    assert pathlets[2].count == 1
    assert pathlets[2].trajectories_included == [3]
    assert pathlets[2].sections == [make_section(third, 0, 1)]


def test_overlapping_assignments_from_one_trajectory_are_counted_once():
    """Union overlapping sections before comparing their new distance."""
    service = SimilarityService()
    first = make_trajectory(1, [(0, 0), (0.25, 0), (0.5, 0), (1, 0)])
    second = make_trajectory(2, [(0, 0.1), (1, 0.1), (2, 0.1), (3, 0.1), (4, 0.1)])
    third = make_trajectory(3, [(0, 1), (6, 1)])
    overlapping = make_candidate([
        make_section(first, 0, 3), make_section(second, 0, 3), make_section(second, 1, 4),
    ])
    six_meters = make_candidate([make_section(third, 0, 1)])

    pathlets = service.select_final_pathlets([overlapping, six_meters], [first, second, third])

    assert len(pathlets) == 2
    # The overlapping candidate covers 1 + 4 = 5 meters, rather than 1 + 3 + 3.
    assert pathlets[0].representative is six_meters.representative
    assert pathlets[1].representative is overlapping.representative
    assert pathlets[1].count == 2
    assert len(pathlets[1].sections) == 2
    assert pathlets[1].sections[1] == make_section(second, 0, 4)


def test_partial_overlap_splits_the_new_sections_at_covered_gaps():
    """Keep both uncovered ends without assigning the covered middle again."""
    service = SimilarityService()
    first = make_trajectory(1, [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (5, 0)])
    second = make_trajectory(2, [(0, 1), (10, 1)])
    middle = make_candidate([make_section(first, 1, 4), make_section(second, 0, 1)])
    full = make_candidate([make_section(first, 0, 5)])

    pathlets = service.select_final_pathlets([full, middle], [first, second])

    assert len(pathlets) == 2
    assert pathlets[0].representative is middle.representative
    assert pathlets[1].representative is full.representative
    assert pathlets[1].count == 1
    assert pathlets[1].sections == [make_section(first, 0, 1), make_section(first, 4, 5)]


def test_already_covered_candidates_are_not_selected_again():
    """Equivalent candidates provide no new coverage after the first selection."""
    service = SimilarityService()
    first = make_trajectory(1, [(0, 0), (1, 0)])
    second = make_trajectory(2, [(0, 0.2), (1, 0.2)])
    candidate = make_candidate([make_section(first, 0, 1), make_section(second, 0, 1)])
    reversed_representative = make_candidate([make_section(second, 0, 1), make_section(first, 0, 1)])

    pathlets = service.select_final_pathlets([candidate, reversed_representative], [first, second])

    assert len(pathlets) == 1
    assert pathlets[0].representative is candidate.representative
    assert pathlets[0].count == 2


def test_uncovered_sections_become_separate_individual_pathlets():
    """Fallback pathlets preserve original indexes and do not bridge represented sections."""
    service = SimilarityService()
    trajectory = make_trajectory(1, [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)])
    middle = make_candidate([make_section(trajectory, 1, 3)])

    pathlets = service.select_final_pathlets([middle], [trajectory])

    assert len(pathlets) == 3
    assert pathlets[0].representative == make_section(trajectory, 1, 3)
    assert pathlets[1].representative == make_section(trajectory, 0, 1)
    assert pathlets[2].representative == make_section(trajectory, 3, 4)
    assert [pathlet.count for pathlet in pathlets] == [1, 1, 1]
    assigned = [
        index
        for pathlet in pathlets
        for section in pathlet.sections
        for index in range(section.start_index, section.end_index)
    ]
    assert len(assigned) == 4
    assert set(assigned) == {0, 1, 2, 3}


def test_trajectories_without_candidates_are_kept_as_individual_pathlets():
    """Preserve complete unrepresented trajectories when no candidates exist."""
    service = SimilarityService()
    first = make_trajectory(1, [(0, 0), (1, 0), (2, 0)])
    second = make_trajectory(2, [(0, 1), (1, 1)])

    pathlets = service.select_final_pathlets([], [first, second])

    assert len(pathlets) == 2
    assert pathlets[0].representative == make_section(first, 0, 2)
    assert pathlets[1].representative == make_section(second, 0, 1)
    assert pathlets[0].trajectories_included == [1]
    assert pathlets[1].trajectories_included == [2]
    assert pathlets[0].count == 1
    assert pathlets[1].count == 1


def test_retracing_the_same_geometry_counts_the_distance_traveled():
    """Different original segment indexes represent separate traveled sections."""
    service = SimilarityService()
    loop = make_trajectory(1, [(0, 0), (1, 0), (0, 0)])
    straight = make_trajectory(2, [(0, 1), (1.5, 1)])
    loop_candidate = make_candidate([make_section(loop, 0, 2)])
    straight_candidate = make_candidate([make_section(straight, 0, 1)])

    pathlets = service.select_final_pathlets([straight_candidate, loop_candidate], [loop, straight])

    assert len(pathlets) == 2
    assert pathlets[0].representative is loop_candidate.representative
    assert pathlets[1].representative is straight_candidate.representative


def test_support_excludes_trajectories_adding_only_zero_distance():
    """Only trajectories contributing positive new length count toward support."""
    service = SimilarityService()
    first = make_trajectory(1, [(0, 0), (1, 0)])
    stationary = make_trajectory(2, [(0, 0.1), (0, 0.1)])
    candidate = make_candidate([make_section(first, 0, 1), make_section(stationary, 0, 1)])

    pathlets = service.select_final_pathlets([candidate], [first, stationary])

    assert len(pathlets) == 1
    assert pathlets[0].count == 1
    assert pathlets[0].trajectories_included == [1]
    assert pathlets[0].sections == [make_section(first, 0, 1)]


def test_zero_length_candidates_stop_selection_and_use_individual_fallback():
    """Zero-length coverage cannot keep the greedy loop running."""
    service = SimilarityService()
    trajectory = make_trajectory(1, [(0, 0), (0, 0), (0, 0)])
    candidate = make_candidate([make_section(trajectory, 0, 2)])

    pathlets = service.select_final_pathlets([candidate], [trajectory])

    assert len(pathlets) == 1
    assert pathlets[0].representative == make_section(trajectory, 0, 2)
    assert pathlets[0].count == 1


def test_no_candidates_or_trajectories_produce_no_pathlets():
    """An empty selection input has no coverage to represent."""
    assert SimilarityService().select_final_pathlets([], []) == []
