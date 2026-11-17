from collections.abc import Sequence

import pytest
from helpers.similarity_steps.pathlet_extension.extension import generate_pathlet as _generate_pathlet
from models.similarity import ProjectedPathlet, ProjectedPoint, ProjectedTrajectory, SupportInterval


def _trajectory(trajectory_id: int, coordinates: Sequence[tuple[float, float]]) -> ProjectedTrajectory:
    """Build a projected trajectory from (x, y) pairs in metres."""
    return ProjectedTrajectory(trajectory_id, [ProjectedPoint(x, y) for x, y in coordinates])


def _generate(trajectories: list[ProjectedTrajectory], epsilon: float) -> list[ProjectedPathlet]:
    """Generate pathlets with greedy (first-match) seed selection."""
    return _generate_pathlet(trajectories, epsilon, greedy_ranking=True)


def _coordinates(pathlet: ProjectedPathlet) -> list[tuple[float, float]]:
    """Return a pathlet's representative as (x, y) pairs."""
    return [(point.x, point.y) for point in pathlet.points]


def test_two_identical_trajectories_give_one_pathlet_with_count_two():
    """The second trajectory supports the first instead of creating new geometry."""
    line = [(0, 0), (10, 0), (20, 0)]

    [pathlet] = _generate([_trajectory(1, line), _trajectory(2, line)], 1)

    assert _coordinates(pathlet) == line
    assert pathlet.count == 2
    assert pathlet.support == [SupportInterval(0, 20, 2)]


def test_reversed_trajectory_gives_its_own_pathlet():
    """Matching only moves forward, so opposite directions of travel stay apart."""
    line = [(0, 0), (10, 0), (20, 0)]

    pathlets = _generate([_trajectory(1, line), _trajectory(2, line[::-1])], 1)

    assert [pathlet.count for pathlet in pathlets] == [1, 1]
    assert [_coordinates(pathlet) for pathlet in pathlets] == [line, line[::-1]]


def test_trajectories_far_apart_give_separate_pathlets():
    """Trajectories with nothing in common stay on their own."""
    pathlets = _generate(
        [_trajectory(1, [(0, 0), (10, 0)]), _trajectory(2, [(500, 500), (510, 500)])],
        1,
    )

    assert [pathlet.count for pathlet in pathlets] == [1, 1]


def test_longest_trajectory_becomes_the_representative():
    """Longer trajectories go first even when a shorter one comes first in the input."""
    long_line = [(0, 0), (10, 0), (20, 0), (30, 0)]

    [pathlet] = _generate([_trajectory(1, [(0, 0), (10, 0)]), _trajectory(2, long_line)], 1)

    assert _coordinates(pathlet) == long_line
    assert pathlet.count == 2
    assert pathlet.support == [SupportInterval(0, 10, 2), SupportInterval(10, 30, 1)]


def test_trajectory_leaving_a_representative_continues_as_a_new_pathlet():
    """The shared part supports the first pathlet and the remainder becomes its own."""
    road = [(0, 0), (10, 0), (20, 0), (30, 0)]
    turning_off = [(0, 0), (10, 0), (10, 10), (10, 20)]

    first, second = _generate([_trajectory(1, road), _trajectory(2, turning_off)], 1)

    assert first.support == [SupportInterval(0, 10, 2), SupportInterval(10, 30, 1)]
    assert _coordinates(second) == [(10, 0), (10, 10), (10, 20)]
    assert second.count == 1
    assert first.count == 2
    assert second.support == [SupportInterval(0, 20, 1)]


def test_trajectory_joining_a_representative_starts_as_a_new_pathlet():
    """The unmatched start becomes a pathlet that ends where the shared part begins."""
    road = [(0, 0), (10, 0), (20, 0), (30, 0)]
    joining = [(0, 10), (0, 0), (10, 0), (20, 0)]

    first, second = _generate([_trajectory(1, road), _trajectory(2, joining)], 1)

    assert first.support == [SupportInterval(0, 20, 2), SupportInterval(20, 30, 1)]
    assert _coordinates(second) == [(0, 10), (0, 0)]
    assert first.count == 2
    assert second.count == 1
    assert second.support == [SupportInterval(0, 10, 1)]


def test_matches_are_measured_against_the_representative_only():
    """A trajectory close to a supporter, but too far from the representative, is not pulled in."""
    pathlets = _generate(
        [
            _trajectory(1, [(0, 0), (10, 0)]),
            _trajectory(2, [(0, 1), (10, 1)]),
            _trajectory(3, [(0, 2), (10, 2)]),
        ],
        1.1,
    )

    assert [pathlet.count for pathlet in pathlets] == [2, 1]


def test_repeated_trajectory_id_counts_as_one_trajectory():
    """Two sections of the same source trajectory are one supporter."""
    line = [(0, 0), (10, 0)]

    [pathlet] = _generate([_trajectory(7, line), _trajectory(7, line)], 1)

    assert pathlet.count == 1
    assert pathlet.support == [SupportInterval(0, 10, 1)]


def test_trajectory_mapping_to_a_single_position_becomes_its_own_pathlet():
    """A crossing that makes no progress along the road does not match it."""
    road = [(0, 0), (10, 0)]
    tiny_crossing = [(5, 0.5), (5, -0.5)]

    first, second = _generate([_trajectory(1, road), _trajectory(2, tiny_crossing)], 1)

    assert first.support == [SupportInterval(0, 10, 1)]
    assert _coordinates(second) == tiny_crossing
    assert second.count == 1


def test_only_stationary_trajectories_are_rejected():
    """Without a single moving segment there is no cell size to build the grid from."""
    stationary = [(0, 0), (0, 0)]

    with pytest.raises(ValueError, match="No non-zero-length segments"):
        _generate([_trajectory(1, stationary), _trajectory(2, stationary)], 0)


def test_empty_input_is_rejected():
    """No trajectories means there is nothing to build the grid from."""
    with pytest.raises(ValueError, match="No non-zero-length segments"):
        _generate([], 1)
