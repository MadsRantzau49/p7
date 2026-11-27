"""One isolated clustering trial. Only the public cluster_routes call is timed."""

import gc
import json
import sys
from contextlib import ExitStack
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

from helpers.similarity_steps.route_clustering import clustering
from helpers.similarity_steps.route_clustering.matching import MatchingCounts
from models.similarity import ProjectedRoute, ProjectedSubtrajectory

from benchmarks.datasets import load_prefix


def validate_members(paths: list[ProjectedSubtrajectory], routes: list[ProjectedRoute]) -> None:
    """Check the complete partition and distinct-trip counts without assuming a specific grouping."""
    remaining = {(p.trajectory_id, p.exit_a_time, p.entry_b_time) for p in paths}
    if len(remaining) != len(paths):
        raise ValueError("Input CSV has duplicate subpath identities")
    for route in routes:
        if not route.members or len(route.points) < 2:
            raise AssertionError("Empty cluster or missing representative geometry")
        if route.count != len({m.trajectory_id for m in route.members}):
            raise AssertionError("Incorrect distinct trajectory count")
        for member in route.members:
            key = member.trajectory_id, member.exit_a_time, member.entry_b_time
            if key not in remaining:
                raise AssertionError("A cluster contains a duplicate or unknown subpath")
            remaining.remove(key)
    if remaining:
        raise AssertionError(f"Lost {len(remaining)} subpaths during clustering")


def _peak_mib() -> float | None:
    # Linux process high-water mark since exec, including input; read before output validation.
    status = Path("/proc/self/status")
    if status.is_file():
        for line in status.read_text().splitlines():
            if line.startswith("VmHWM:"):
                return round(int(line.split()[1]) / 1024, 2)
    return None


def _instrument(stack: ExitStack, stats: dict, counts: MatchingCounts) -> None:
    # Wrap only the stage boundaries, and only in the separate diagnostic process.
    original_grid = clustering.build_global_grid
    original_assign = clustering.assign_clusters

    def grid(entries, epsilon):
        t = perf_counter()
        result = original_grid(entries, epsilon)
        stats["grid_s"] = perf_counter() - t
        stats["grid_cell_m"] = result.cell_size if result is not None else None
        stats["path_cell_pairs"] = sum(result.popularity.values()) if result is not None else 0
        return result

    def assign(entries, epsilon):
        t = perf_counter()
        result = original_assign(entries, epsilon, counts)
        stats["assign_s"] = perf_counter() - t
        return result

    stack.enter_context(patch.object(clustering, "build_global_grid", grid))
    stack.enter_context(patch.object(clustering, "assign_clusters", assign))


def run(path: Path, size: int | None, epsilon: float, max_points: int, profile: bool) -> dict:
    """Run once on already loaded metre coordinates; return measurements and checked output sizes."""
    paths, digest = load_prefix(path, size, max_points)
    points = sum(len(p.projected_points) for p in paths)
    stats = {}
    counts = MatchingCounts()
    gc.collect()
    with ExitStack() as stack:
        if profile:
            _instrument(stack, stats, counts)
        start = perf_counter()
        routes = clustering.cluster_routes(paths, epsilon)
        elapsed = perf_counter() - start
    peak = _peak_mib()
    validate_members(paths, routes)
    if profile:
        stats.update(
            candidate_checks=counts.bounds_rejections + counts.comparisons,
            frechet_runs=counts.free_space_runs,
        )
    return dict(
        prefix_sha256=digest,
        paths=len(paths),
        points=points,
        clusters=len(routes),
        elapsed_s=elapsed,
        peak_rss_mib=peak,
        **stats,
    )


if __name__ == "__main__":
    _, filename, n, eps, point_limit, mode = sys.argv
    print(
        json.dumps(
            run(
                Path(filename),
                None if n == "all" else int(n),
                float(eps),
                int(point_limit),
                mode == "profile",
            )
        )
    )
