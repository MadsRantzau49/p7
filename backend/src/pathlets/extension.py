"""Bounded, directed overlap extension with fractional source intervals.

Whole-segment stars guide seeds. Nearby pairs also supply clipped seeds because
unequal sampling can make whole-segment SSPD fail on an identical corridor.
This is a geometric heuristic, not exhaustive subtrajectory enumeration.
"""

from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from math import hypot

from .geometry import interpolate, interval_coordinates, length, project_fraction, sspd
from .models import (
    XY,
    Assignment,
    CandidateCluster,
    ClusteringConfig,
    ExtendedPathletCandidate,
    MetricTrajectory,
    Pair,
    Segment,
)

POSITION_TOLERANCE = 1e-9


@dataclass(frozen=True)
class DirectedOverlap:
    representative: Assignment
    other: Assignment
    segment_id: int


def _overlap(first: Segment, second: Segment, config: ClusteringConfig) -> DirectedOverlap | None:
    dx, dy = first.end[0] - first.start[0], first.end[1] - first.start[1]
    ex, ey = second.end[0] - second.start[0], second.end[1] - second.start[1]
    denominator = hypot(dx, dy) * hypot(ex, ey)
    if not denominator or (dx * ex + dy * ey) <= 0:
        return None
    if (dx * ex + dy * ey) / denominator < config.direction_cosine_min:
        return None
    start = max(0.0, project_fraction(second.start, first.start, first.end))
    end = min(1.0, project_fraction(second.end, first.start, first.end))
    if end - start <= POSITION_TOLERANCE:
        return None
    first_coordinates = (interpolate(first.start, first.end, start), interpolate(first.start, first.end, end))
    other_start, other_end = (
        max(0.0, min(1.0, project_fraction(point, second.start, second.end))) for point in first_coordinates
    )
    if other_end - other_start <= POSITION_TOLERANCE:
        return None
    other_coordinates = (
        interpolate(second.start, second.end, other_start),
        interpolate(second.start, second.end, other_end),
    )
    if sspd(first_coordinates, other_coordinates) > config.epsilon_m:
        return None
    return DirectedOverlap(
        Assignment(first.trajectory_id, first.segment_index + start, first.segment_index + end),
        Assignment(
            second.trajectory_id, second.segment_index + other_start, second.segment_index + other_end
        ),
        first.segment_id,
    )


def generate_overlap_atoms(
    clusters: list[CandidateCluster],
    segments: list[Segment],
    nearby_pairs: list[Pair],
    trajectories: list[MetricTrajectory],
    config: ClusteringConfig,
) -> list[ExtendedPathletCandidate]:
    """Partition each representative at support changes and sampling boundaries.

    Multiple visits by the same other trajectory compete deterministically for
    one assignment, rather than inflating support. Fractional positions keep
    different sampling boundaries and repeated visits distinguishable.
    """
    by_id = {segment.segment_id: segment for segment in segments}
    by_trajectory = {trajectory.trajectory_id: trajectory for trajectory in trajectories}
    matched_pairs = {
        tuple(sorted((cluster.representative_id, member)))
        for cluster in clusters
        for member in cluster.member_ids
        if member != cluster.representative_id
    }
    # Star edges first, followed by supplemental spatially discovered overlaps.
    pairs = sorted(matched_pairs) + [pair for pair in nearby_pairs if pair not in matched_pairs]
    overlaps: dict[int, list[DirectedOverlap]] = defaultdict(list)
    for first_id, second_id in pairs:
        first, second = by_id[first_id], by_id[second_id]
        for representative, other in ((first, second), (second, first)):
            overlap = _overlap(representative, other, config)
            if overlap is not None:
                overlaps[representative.segment_id].append(overlap)

    atoms: list[ExtendedPathletCandidate] = []
    for segment_id, local in sorted(overlaps.items()):
        segment = by_id[segment_id]
        # Sweep intervals instead of scanning all local overlaps for every cut.
        starts: dict[float, list[int]] = defaultdict(list)
        ends: dict[float, list[int]] = defaultdict(list)
        for index, overlap in enumerate(local):
            starts[overlap.representative.start].append(index)
            ends[overlap.representative.end].append(index)
        cuts = sorted(starts.keys() | ends.keys())
        active: set[int] = set()
        for start, end in zip(cuts, cuts[1:], strict=False):
            active.difference_update(ends.get(start, ()))
            active.update(starts.get(start, ()))
            if end - start <= POSITION_TOLERANCE:
                continue
            representative = Assignment(segment.trajectory_id, start, end)
            representative_coordinates = interval_coordinates(
                by_trajectory[segment.trajectory_id], representative
            )
            best: dict[str, tuple[float, Assignment]] = {}
            for index in sorted(active):
                overlap = local[index]
                span = overlap.representative.end - overlap.representative.start
                other_span = overlap.other.end - overlap.other.start
                assignment = Assignment(
                    overlap.other.trajectory_id,
                    overlap.other.start + (start - overlap.representative.start) / span * other_span,
                    overlap.other.start + (end - overlap.representative.start) / span * other_span,
                )
                distance = sspd(
                    representative_coordinates,
                    interval_coordinates(by_trajectory[assignment.trajectory_id], assignment),
                )
                if distance > config.epsilon_m:
                    continue
                proposal = (distance, assignment)
                previous = best.get(assignment.trajectory_id)
                if previous is None or proposal < previous:
                    best[assignment.trajectory_id] = proposal
            if best:
                assignments = tuple(sorted((representative, *(value[1] for value in best.values()))))
                atoms.append(
                    ExtendedPathletCandidate(
                        representative, assignments, (segment_id,), max(value[0] for value in best.values())
                    )
                )
    return sorted(atoms, key=lambda atom: atom.representative)


def _join(
    first: ExtendedPathletCandidate,
    second: ExtendedPathletCandidate,
    trajectories: dict[str, MetricTrajectory],
    gap_m: float,
) -> ExtendedPathletCandidate | None:
    if first.representative.trajectory_id != second.representative.trajectory_id:
        return None
    if len(first.assignments) != len(second.assignments):
        return None
    assignments: list[Assignment] = []
    for previous, following in zip(first.assignments, second.assignments, strict=True):
        if previous.trajectory_id != following.trajectory_id:
            return None
        # Overlapping seed intervals can be united, but every source must
        # progress forward. Positive gaps are included, never silently skipped.
        if following.start < previous.start - POSITION_TOLERANCE:
            return None
        if following.end <= previous.end + POSITION_TOLERANCE:
            return None
        if following.start > previous.end + POSITION_TOLERANCE:
            gap = Assignment(previous.trajectory_id, previous.end, following.start)
            if length(interval_coordinates(trajectories[gap.trajectory_id], gap)) > gap_m:
                return None
        assignments.append(Assignment(previous.trajectory_id, previous.start, following.end))
    return ExtendedPathletCandidate(
        Assignment(first.representative.trajectory_id, first.representative.start, second.representative.end),
        tuple(assignments),
        tuple(dict.fromkeys((*first.seed_segment_ids, *second.seed_segment_ids))),
        0.0,
    )


def extend_clusters(
    clusters: list[CandidateCluster],
    trajectories: list[MetricTrajectory],
    segments: list[Segment],
    nearby_pairs: list[Pair],
    config: ClusteringConfig,
) -> list[ExtendedPathletCandidate]:
    """Try at most N consecutive atoms from each start, checking every prefix.

    Failed SSPD prefixes do NOT terminate exploration: a longer prefix may pass.
    Support changes or gaps above the configured metric bound define boundaries.
    Retain the atom and longest valid prefix at each start, bounding stored
    candidates to twice the atom count. This deliberately omits other valid
    interval combinations and does not claim completeness or optimality.
    """
    atoms = generate_overlap_atoms(clusters, segments, nearby_pairs, trajectories, config)
    by_id = {trajectory.trajectory_id: trajectory for trajectory in trajectories}

    @lru_cache(maxsize=65536)
    def coordinates(assignment: Assignment) -> tuple[XY, ...]:
        return interval_coordinates(by_id[assignment.trajectory_id], assignment)

    @lru_cache(maxsize=65536)
    def distance(first: Assignment, second: Assignment) -> float:
        return sspd(coordinates(first), coordinates(second))

    extended: list[ExtendedPathletCandidate] = []
    for index, atom in enumerate(atoms):
        current = atom
        longest = atom
        for following in atoms[index + 1 : index + config.max_extension_steps]:
            joined = _join(current, following, by_id, config.gap_m)
            if joined is None:
                break
            current = joined
            maximum = max(
                distance(joined.representative, assignment)
                for assignment in joined.assignments
                if assignment != joined.representative
            )
            if maximum <= config.epsilon_m:
                longest = ExtendedPathletCandidate(
                    joined.representative, joined.assignments, joined.seed_segment_ids, maximum
                )
        extended.append(atom)
        if longest != atom:
            extended.append(longest)
    return extended
