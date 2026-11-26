import math
from collections import Counter
from dataclasses import dataclass
from operator import itemgetter

from helpers.similarity_steps.route_clustering.geometry import (
    Cell,
    cell_index,
    polyline_cell_visit_bound,
    polyline_cells,
)
from helpers.similarity_steps.route_clustering.matching import MatchingCounts, routes_match
from models.similarity import (
    Cluster,
    ClusteredSubtrajectory,
    Polyline,
    ProjectedRoute,
    ProjectedSubtrajectory,
)

# This limits both traversal work and retained cells, even when every cell is unique.
MAX_GRID_CELL_VISITS = 6_000_000


@dataclass(frozen=True)
class PopularityGrid:
    """Distinct cells per input subtrajectory and the number of users of each cell."""

    cell_size: float
    cells_by_entry: list[set[Cell]]
    popularity: Counter[Cell]


def cluster_routes(subtrajectories: list[ProjectedSubtrajectory], epsilon: float) -> list[ProjectedRoute]:
    """Group whole subtrajectories into routes within epsilon metres of each other.

    Popular routes are considered first as potential representatives. The service runs the
    same stages individually to log their timings.
    """
    entries = build_polylines(subtrajectories)
    entries = order_by_popularity(entries, build_global_grid(entries, epsilon))
    return build_routes(assign_clusters(entries, epsilon))


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


def build_global_grid(entries: list[ClusteredSubtrajectory], epsilon: float) -> PopularityGrid | None:
    """Bound popularity grid work independently of the matching tolerance."""
    if math.isnan(epsilon):
        raise ValueError("Epsilon must not be NaN.")
    if epsilon <= 0:
        return None

    cell_size = _popularity_cell_size(entries, epsilon)
    if cell_size is None:
        return None
    popularity: Counter[Cell] = Counter()
    cells_by_entry: list[set[Cell]] = []
    for entry in entries:
        cells = polyline_cells(entry.polyline, cell_size)
        cells_by_entry.append(cells)
        popularity.update(cells)
    return PopularityGrid(cell_size, cells_by_entry, popularity)


def _grid_fits(entries: list[ClusteredSubtrajectory], cell_size: float) -> bool:
    visits = 0
    for entry in entries:
        visits += polyline_cell_visit_bound(entry.polyline, cell_size)
        if visits > MAX_GRID_CELL_VISITS:
            return False
    return True


def _popularity_cell_size(entries: list[ClusteredSubtrajectory], epsilon: float) -> float | None:
    if _grid_fits(entries, epsilon):
        return epsilon

    # When epsilon is tiny, start near the distance we can afford to traverse per cell.
    total_length = sum(entry.polyline.total_length for entry in entries)
    cell_size = max(2 * epsilon, total_length / MAX_GRID_CELL_VISITS)
    farthest = max(
        (max(abs(point.x), abs(point.y)) for entry in entries for point in entry.polyline.points),
        default=0.0,
    )
    while not _grid_fits(entries, cell_size):
        # Beyond this extent, all finite widths produce the same four cells around the
        # origin. If the grid still needs too much work, keep input order and match anyway.
        if cell_size > farthest:
            return None
        cell_size *= 2
    return cell_size


def order_by_popularity(
    entries: list[ClusteredSubtrajectory], grid: PopularityGrid | None
) -> list[ClusteredSubtrajectory]:
    """Sort by global overlap, then trajectory ID and the A/B crossing times."""
    if grid is None:
        return entries

    def sort_key(item: tuple[ClusteredSubtrajectory, set[Cell]]) -> tuple[int, int, str, str]:
        entry, cells = item
        score = sum(grid.popularity[cell] - 1 for cell in cells)
        member = entry.member
        return -score, member.trajectory_id, member.exit_a_time.isoformat(), member.entry_b_time.isoformat()

    ranked = sorted(zip(entries, grid.cells_by_entry, strict=True), key=sort_key)
    return [entry for entry, _ in ranked]


def assign_clusters(
    entries: list[ClusteredSubtrajectory], epsilon: float, counts: MatchingCounts | None = None
) -> list[Cluster]:
    """Place each ordered entry with the first representative it matches, or make it one."""
    clusters: list[Cluster] = []
    # A matching start is at most epsilon away. Width 2*epsilon leaves room even for
    # rounding in the matcher's distance calculation: a match cannot be two cells away.
    cell_size = 2 * epsilon
    index: dict[Cell, list[tuple[int, _Bounds]]] | None = {} if 0 < cell_size < math.inf else None
    for entry in entries:
        line = entry.polyline
        if index is not None and line.points:
            start = line.points[0]
            cell = cell_index(start.x, cell_size), cell_index(start.y, cell_size)
            bounds = _Bounds.from_polyline(line)
            cluster = _indexed_match(line, bounds, clusters, index, cell, epsilon, counts)
            if cluster is None:
                index.setdefault(cell, []).append((len(clusters), bounds))
        else:
            cluster = next(
                (
                    cluster
                    for cluster in clusters
                    if routes_match(line, cluster.representative, epsilon, counts)
                ),
                None,
            )
        if cluster is None:
            clusters.append(Cluster(representative=line, members=[entry.member]))
        else:
            cluster.members.append(entry.member)

    return clusters


def build_routes(clusters: list[Cluster]) -> list[ProjectedRoute]:
    """Return each cluster's permanent representative, distinct trajectory count, and members."""
    routes: list[ProjectedRoute] = []
    for cluster in clusters:
        count = len({member.trajectory_id for member in cluster.members})
        routes.append(
            ProjectedRoute(points=cluster.representative.points, count=count, members=cluster.members)
        )

    return routes


@dataclass(frozen=True, slots=True)
class _Bounds:
    min_x: float
    max_x: float
    min_y: float
    max_y: float

    @classmethod
    def from_polyline(cls, line: Polyline) -> "_Bounds":
        first = line.points[0]
        min_x = max_x = first.x
        min_y = max_y = first.y
        for point in line.points:
            x, y = point.x, point.y
            if x < min_x:
                min_x = x
            elif x > max_x:
                max_x = x
            if y < min_y:
                min_y = y
            elif y > max_y:
                max_y = y
        return cls(min_x, max_x, min_y, max_y)

    def differs_by_more_than(self, other: "_Bounds", epsilon: float) -> bool:
        # If the routes match, every extreme point must have a counterpart on the
        # other curve at most epsilon away. A curve's extrema occur at its vertices.
        return (
            abs(self.min_x - other.min_x) > epsilon
            or abs(self.max_x - other.max_x) > epsilon
            or abs(self.min_y - other.min_y) > epsilon
            or abs(self.max_y - other.max_y) > epsilon
        )


def _indexed_match(
    line: Polyline,
    bounds: _Bounds,
    clusters: list[Cluster],
    index: dict[Cell, list[tuple[int, _Bounds]]],
    cell: Cell,
    epsilon: float,
    counts: MatchingCounts | None,
) -> Cluster | None:
    """Try the nearby representatives in their original creation order."""
    x, y = cell
    candidates = [
        candidate
        for column in range(x - 1, x + 2)
        for row in range(y - 1, y + 2)
        for candidate in index.get((column, row), ())
    ]
    candidates.sort(key=itemgetter(0))
    for considered, (i, representative_bounds) in enumerate(candidates, start=1):
        if bounds.differs_by_more_than(representative_bounds, epsilon):
            if counts is not None:
                counts.bounds_rejections += 1
            continue
        if routes_match(line, clusters[i].representative, epsilon, counts):
            if counts is not None:
                counts.endpoint_bucket_skips += i + 1 - considered
            return clusters[i]
    if counts is not None:
        counts.endpoint_bucket_skips += len(clusters) - len(candidates)
    return None
