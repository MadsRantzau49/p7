from models.similarity import SupportInterval, TrajectorySection


def merge_intervals(intervals: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Return sorted intervals with overlaps and touching endpoints merged.

    Expect each interval as (start, end) with start <= end.
    Return an empty list when no intervals are supplied.
    """
    if not intervals:
        return []
    ordered = sorted(intervals)
    merged = []
    start, end = ordered[0]
    for next_start, next_end in ordered[1:]:
        if next_start <= end:
            end = max(end, next_end)
        else:
            merged.append((start, end))
            start, end = next_start, next_end
    merged.append((start, end))
    return merged


def support_intervals(sections: list[TrajectorySection], total_length: float) -> list[SupportInterval]:
    """Build intervals with constant counts of distinct supporting trajectories.

    Group sections by trajectory ID and merge each trajectory's coverage,
    so overlapping contributions from the same trajectory count once.

    Create +1 events at coverage starts and -1 events at coverage ends.
    Sweep these events in distance order, emitting intervals between them
    and joining adjacent intervals with equal counts.

    All offsets and total_length use metres. For a zero-length representative,
    return one [0.0, 0.0] interval counting all distinct IDs in sections.
    """
    intervals_by_trajectory: dict[int, list[tuple[float, float]]] = {}

    for section in sections:
        intervals_by_trajectory.setdefault(section.trajectory_id, []).append(
            (section.representative_start_m, section.representative_end_m)
        )
    if total_length == 0:
        return [SupportInterval(0.0, 0.0, len(intervals_by_trajectory))]

    count_changes: dict[float, int] = {}
    for intervals in intervals_by_trajectory.values():
        for start, end in merge_intervals(intervals):
            count_changes[start] = count_changes.get(start, 0) + 1
            count_changes[end] = count_changes.get(end, 0) - 1

    support: list[SupportInterval] = []
    previous = 0.0
    count = 0
    for position, change in sorted(count_changes.items()):
        if position > previous:
            if support and support[-1].count == count:
                support[-1].end_m = position
            else:
                support.append(SupportInterval(previous, position, count))
        count += change
        previous = position
    return support
