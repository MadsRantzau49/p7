"""R-tree broad phase and exact whole-segment SSPD narrow phase."""

from dataclasses import dataclass
from itertools import combinations

from shapely.geometry import LineString, Point, box
from shapely.strtree import STRtree

from .geometry import sspd
from .models import CandidateCluster, ClusteringConfig, Pair, Segment, SegmentMatch


@dataclass(frozen=True)
class SpatialIndex:
    tree: STRtree
    segment_ids: tuple[int, ...]


def build_spatial_index(segments: list[Segment]) -> SpatialIndex:
    """Bulk-load all segment geometries; tree positions are not segment IDs."""
    geometries = [Point(s.start) if s.start == s.end else LineString((s.start, s.end)) for s in segments]
    return SpatialIndex(STRtree(geometries), tuple(s.segment_id for s in segments))


def find_nearby_pairs(
    segments: list[Segment], spatial_index: SpatialIndex, config: ClusteringConfig
) -> list[Pair]:
    """Query expanded bounding boxes, retaining each cross-trajectory pair once.

    SSPD for two endpoints is the sum of four distances divided by four.
    Thus every distance is <= 4 epsilon for a valid pair, which proves this
    conservative bounding-box radius cannot miss a whole-segment SSPD match.

    With the distance filter disabled, query the complete dataset extent once
    and enumerate every cross-source pair from the returned index entries.
    The tree is still built/queried, but cannot reject distant pairs in this mode.
    """
    if not config.use_bounding_box_filter:
        if not segments:
            return []
        by_id = {segment.segment_id: segment for segment in segments}
        bounds = [segment.bounds for segment in segments]
        x0, y0 = min(b[0] for b in bounds), min(b[1] for b in bounds)
        x1, y1 = max(b[2] for b in bounds), max(b[3] for b in bounds)
        extent = Point(x0, y0) if (x0, y0) == (x1, y1) else box(x0, y0, x1, y1)
        positions = spatial_index.tree.query(extent)
        return all_cross_trajectory_pairs([by_id[spatial_index.segment_ids[int(p)]] for p in positions])
    by_id = {segment.segment_id: segment for segment in segments}
    result: list[Pair] = []
    radius = config.radius_m
    for segment in segments:
        x0, y0, x1, y1 = segment.bounds
        query = box(x0 - radius, y0 - radius, x1 + radius, y1 + radius)
        # Query every intersecting branch, never just one internal R-tree group.
        for position in spatial_index.tree.query(query):
            other_id = spatial_index.segment_ids[int(position)]
            if other_id > segment.segment_id and by_id[other_id].trajectory_id != segment.trajectory_id:
                result.append((segment.segment_id, other_id))
    return sorted(result)


def all_cross_trajectory_pairs(segments: list[Segment]) -> list[Pair]:
    """Enumerate all unique cross-source pairs without inspecting any coordinates."""
    ordered = sorted(segments, key=lambda segment: segment.segment_id)
    return [
        (first.segment_id, second.segment_id)
        for first, second in combinations(ordered, 2)
        if first.trajectory_id != second.trajectory_id
    ]


def find_nearby_pairs_brute_force(segments: list[Segment], config: ClusteringConfig) -> list[Pair]:
    """Scan every cross-source pair without building or querying a spatial index.

    When filtering is enabled, use the indexed mode's expanded-box predicate so
    downstream SSPD, overlap extension, and pathlets are identical. Only discovery
    changes: this reference baseline takes O(n²) time, caching O(n) bounds and
    storing only the accepted candidates. When filtering is disabled, return
    all cross-source pairs without reading segment bounds or the search radius.
    """
    if not config.use_bounding_box_filter:
        return all_cross_trajectory_pairs(segments)
    boxes = [(s.segment_id, s.trajectory_id, s.bounds) for s in sorted(segments, key=lambda s: s.segment_id)]
    radius = config.radius_m
    result: list[Pair] = []
    for (first_id, first_trajectory, first), (second_id, second_trajectory, second) in combinations(boxes, 2):
        if first_trajectory == second_trajectory:
            continue
        ax0, ay0, ax1, ay1 = first
        bx0, by0, bx1, by1 = second
        if ax0 - radius <= bx1 and bx0 <= ax1 + radius and ay0 - radius <= by1 and by0 <= ay1 + radius:
            result.append((first_id, second_id))
    return result


def compare_sspd(pairs: list[Pair], segments: list[Segment], epsilon_m: float) -> list[SegmentMatch]:
    """Accept distances <= epsilon, including exact equality."""
    by_id = {segment.segment_id: segment for segment in segments}
    matches: list[SegmentMatch] = []
    for first_id, second_id in pairs:
        first, second = by_id[first_id], by_id[second_id]
        distance = sspd((first.start, first.end), (second.start, second.end))
        if distance <= epsilon_m:
            matches.append(SegmentMatch(first_id, second_id, distance))
    return matches


def construct_candidate_clusters(
    segments: list[Segment], matches: list[SegmentMatch]
) -> list[CandidateCluster]:
    """Build independent representative stars, never transitive components."""
    by_id = {segment.segment_id: segment for segment in segments}
    neighbors = {segment.segment_id: [segment.segment_id] for segment in segments}
    for match in matches:
        neighbors[match.first_id].append(match.second_id)
        neighbors[match.second_id].append(match.first_id)
    return [
        CandidateCluster(
            segment.segment_id,
            tuple(sorted(neighbors[segment.segment_id])),
            tuple(sorted({by_id[i].trajectory_id for i in neighbors[segment.segment_id]})),
        )
        for segment in segments
    ]
