from helpers.similarity_steps.pathlet_extension.support import merge_intervals, support_intervals
from models.similarity import SupportInterval, TrajectorySection


def _section(trajectory_id: int, start_m: float, end_m: float) -> TrajectorySection:
    """Build one trajectory's coverage of a representative."""
    return TrajectorySection(trajectory_id, start_m, end_m)


def test_merge_intervals_of_nothing_is_empty():
    """No intervals in means no intervals out."""
    assert merge_intervals([]) == []


def test_merge_intervals_joins_overlapping_and_touching_intervals():
    """Intervals that overlap or share an endpoint become one."""
    assert merge_intervals([(0, 5), (3, 8), (8, 10)]) == [(0, 10)]


def test_merge_intervals_sorts_and_keeps_separate_intervals_apart():
    """A real gap is preserved and the result is in distance order."""
    assert merge_intervals([(6, 8), (0, 2)]) == [(0, 2), (6, 8)]


def test_overlapping_sections_of_one_trajectory_count_once():
    """A trajectory covering the same stretch twice is still one supporter."""
    sections = [_section(1, 0, 10), _section(1, 5, 15)]

    assert support_intervals(sections, 15) == [SupportInterval(0, 15, 1)]


def test_two_trajectories_on_the_same_stretch_count_twice():
    """Two different trajectories give a count of 2."""
    sections = [_section(1, 0, 10), _section(2, 0, 10)]

    assert support_intervals(sections, 10) == [SupportInterval(0, 10, 2)]


def test_count_changes_where_a_supporter_joins_or_leaves():
    """Partial support splits the representative into stretches with their own counts."""
    sections = [_section(1, 0, 30), _section(2, 10, 20)]

    assert support_intervals(sections, 30) == [
        SupportInterval(0, 10, 1),
        SupportInterval(10, 20, 2),
        SupportInterval(20, 30, 1),
    ]


def test_neighbouring_stretches_with_the_same_count_are_joined():
    """One trajectory taking over from another does not split the interval."""
    sections = [_section(1, 0, 10), _section(2, 10, 20)]

    assert support_intervals(sections, 20) == [SupportInterval(0, 20, 1)]


def test_uncovered_gap_has_a_count_of_zero():
    """Stretches between coverage are reported with no supporters."""
    sections = [_section(1, 0, 2), _section(1, 8, 10)]

    assert support_intervals(sections, 10) == [
        SupportInterval(0, 2, 1),
        SupportInterval(2, 8, 0),
        SupportInterval(8, 10, 1),
    ]


def test_zero_length_section_adds_no_support_on_a_normal_representative():
    """A section that maps to a single position covers no distance."""
    sections = [_section(1, 0, 10), _section(2, 5, 5)]

    assert support_intervals(sections, 10) == [SupportInterval(0, 10, 1)]


def test_zero_length_representative_counts_all_distinct_trajectories():
    """A representative without length gets one [0, 0] interval counting each trajectory once."""
    sections = [_section(1, 0, 0), _section(1, 0, 0), _section(2, 0, 0)]

    assert support_intervals(sections, 0) == [SupportInterval(0.0, 0.0, 2)]
