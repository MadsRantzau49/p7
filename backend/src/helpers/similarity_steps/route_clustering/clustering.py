from collections import Counter
from dataclasses import dataclass

from helpers.similarity_steps.route_clustering.geometry import polyline_cells
from helpers.similarity_steps.route_clustering.matching import MatchingCounts, routes_match
from models.similarity import (
    Cluster,
    ClusteredSubtrajectory,
    Polyline,
    ProjectedRoute,
    ProjectedSubtrajectory,
)


@dataclass
class GridCounts:
    """Aggregate grid usage across the representative-selection stage."""

    member_cell_visits: int = 0
    occupied_cells_summed_across_clusters: int = 0
    peak_members_in_cell_within_cluster: int = 0


def cluster_routes(subtrajectories: list[ProjectedSubtrajectory], epsilon: float) -> list[ProjectedRoute]:
    """Group whole subtrajectories into routes within epsilon metres of each other.

    This runs the clustering stages in order: prepare the polylines, assign them to clusters,
    choose each cluster's representative, then assemble the routes. The service runs the same
    stages one at a time so each is timed and logged on its own; this wrapper keeps the whole
    pipeline available as one call.
    """
    entries = build_polylines(subtrajectories)
    clusters = assign_clusters(entries, epsilon)
    representatives = choose_representatives(clusters, epsilon)
    return build_routes(clusters, representatives)


def build_polylines(
    subtrajectories: list[ProjectedSubtrajectory],
) -> list[ClusteredSubtrajectory]:
    """Pair each subtrajectory with its projected polyline, rejecting stationary-only input."""
    entries = [
        ClusteredSubtrajectory(subtrajectory.member, Polyline.from_points(subtrajectory.projected_points))
        for subtrajectory in subtrajectories
    ]

    if not any(length > 0 for entry in entries for length in entry.polyline.segment_lengths):
        raise ValueError(
            "No non-zero-length segments: subtrajectories are empty, single-point, or stationary"
        )

    return entries


def assign_clusters(
    entries: list[ClusteredSubtrajectory], epsilon: float, counts: MatchingCounts | None = None
) -> list[Cluster]:
    """Place each entry in the first cluster whose anchor it matches, else start a new one."""
    clusters: list[Cluster] = []
    for entry in entries:
        cluster = _matching_cluster(entry.polyline, clusters, epsilon, counts)
        if cluster is not None:
            cluster.members.append(entry)
        else:
            clusters.append(Cluster(anchor=entry.polyline, members=[entry]))

    return clusters


def choose_representatives(
    clusters: list[Cluster],
    epsilon: float,
    counts: GridCounts | None = None,
) -> list[Polyline]:
    """Pick each cluster's representative by grid-cell overlap, one per cluster in order."""
    return [_representative(cluster, epsilon, counts) for cluster in clusters]


def build_routes(clusters: list[Cluster], representatives: list[Polyline]) -> list[ProjectedRoute]:
    """Assemble each cluster into a route with its representative, distinct count and members."""
    routes: list[ProjectedRoute] = []
    for cluster, representative in zip(clusters, representatives, strict=True):
        members = [entry.member for entry in cluster.members]
        count = len({member.trajectory_id for member in members})
        routes.append(ProjectedRoute(points=representative.points, count=count, members=members))

    return routes


def _matching_cluster(
    polyline: Polyline, clusters: list[Cluster], epsilon: float, counts: MatchingCounts | None
) -> Cluster | None:
    """Return the first cluster whose anchor matches the polyline, or None."""
    for cluster in clusters:
        if routes_match(polyline, cluster.anchor, epsilon, counts):
            return cluster
    return None


def _representative(
    cluster: Cluster,
    epsilon: float,
    counts: GridCounts | None,
) -> Polyline:
    """Return the member polyline that shares the most grid cells with the other members.

    Each cell is weighted by how many members pass through it, and a member scores the sum of
    the weights of its cells, so the most typical path wins. Ties go to the lowest trajectory
    id, which keeps the choice reproducible for NF6.
    """
    if epsilon <= 0:
        return cluster.members[0].polyline

    member_cells = [polyline_cells(entry.polyline, epsilon) for entry in cluster.members]
    popularity: Counter[tuple[int, int]] = Counter()
    for cells in member_cells:
        popularity.update(cells)

    if counts is not None:
        counts.member_cell_visits += sum(map(len, member_cells))
        counts.occupied_cells_summed_across_clusters += len(popularity)
        counts.peak_members_in_cell_within_cluster = max(
            counts.peak_members_in_cell_within_cluster, max(popularity.values(), default=0)
        )
    best_index = 0
    best_key: tuple[int, int] | None = None
    for index, (entry, cells) in enumerate(zip(cluster.members, member_cells, strict=True)):
        score = sum(popularity[cell] for cell in cells)
        key = (score, -entry.member.trajectory_id)
        if best_key is None or key > best_key:
            best_key = key
            best_index = index

    return cluster.members[best_index].polyline
