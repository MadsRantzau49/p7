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
    """Build intervals with constant sets of distinct supporting trajectories.

    Group sections by trajectory ID and merge each trajectory's coverage,
    so overlapping contributions from the same trajectory count once.

    Sweep coverage starts and ends in distance order. Keep a boundary when
    supporters change, even if the number of supporters stays the same.

    All offsets and total_length use metres. For a zero-length representative,
    return one [0.0, 0.0] interval counting all distinct IDs in sections.
    """
    intervals_by_trajectory: dict[int, list[tuple[float, float]]] = {}

    for section in sections:
        intervals_by_trajectory.setdefault(section.trajectory_id, []).append(
            (section.representative_start_m, section.representative_end_m)
        )
    if total_length == 0:
        ids = sorted(intervals_by_trajectory)
        return [SupportInterval(0.0, 0.0, len(ids), ids)]

    starts: dict[float, set[int]] = {}
    ends: dict[float, set[int]] = {}
    for trajectory_id, intervals in intervals_by_trajectory.items():
        for start, end in merge_intervals(intervals):
            start, end = max(0.0, start), min(total_length, end)
            if end <= start:
                continue
            starts.setdefault(start, set()).add(trajectory_id)
            ends.setdefault(end, set()).add(trajectory_id)

    support: list[SupportInterval] = []
    previous = 0.0
    active: set[int] = set()
    for position in sorted({0.0, total_length} | starts.keys() | ends.keys()):
        if position > previous:
            ids = sorted(active)
            if support and support[-1].trajectory_ids == ids:
                support[-1].end_m = position
            else:
                support.append(SupportInterval(previous, position, len(ids), ids))
        active.difference_update(ends.get(position, ()))
        active.update(starts.get(position, ()))
        previous = position
    return support
