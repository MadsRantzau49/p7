"""Central replaceable-stage pipeline and command-line entry point."""

import argparse
import logging
from collections.abc import Callable
from pathlib import Path
from time import perf_counter
from typing import TypeVar

from .extension import extend_clusters
from .geometry import convert_to_meters, generate_segments
from .loading import load_trajectories
from .models import ClusteringConfig, ClusteringResult, GPSTrajectory, PipelineMetrics
from .output import write_json
from .selection import convert_to_gps, select_final_pathlets, validate_coverage
from .spatial import build_spatial_index, compare_sspd, construct_candidate_clusters, find_nearby_pairs

LOGGER = logging.getLogger(__name__)
T = TypeVar("T")
STAGE_NAMES = (
    "metric_trajectories",
    "segments",
    "bounding_boxes",
    "nearby_pairs",
    "sspd_matches",
    "candidate_clusters",
    "extended_pathlets",
    "selected_pathlets",
    "final_gps_pathlets",
)


def run_pipeline(
    config: ClusteringConfig,
    trajectories: list[GPSTrajectory] | None = None,
) -> ClusteringResult:
    """Execute all nine stages; optionally accept already loaded backend data.

    No plotting imports or rendering occur when debug is disabled. The optional
    debug observer reads completed intermediate results without modifying them.
    """
    started = perf_counter()
    runtimes: dict[str, float] = {}

    def timed(name: str, operation: Callable[[], T]) -> T:
        start = perf_counter()
        value = operation()
        runtimes[name] = (perf_counter() - start) * 1000
        LOGGER.info("%s: %.2f ms", name, runtimes[name])
        return value

    def load() -> list[GPSTrajectory]:
        if trajectories is not None:
            return trajectories
        if config.input_path is None:
            raise ValueError("input_path is required when trajectories are not supplied")
        return load_trajectories(config.input_path)

    gps = timed("00_load", load)
    metric, projection = timed(
        "01_projection", lambda: convert_to_meters(gps, config.max_projection_radius_m)
    )
    segments = timed("02_segments", lambda: generate_segments(metric))
    spatial_index = timed("03_spatial_index", lambda: build_spatial_index(segments))
    pairs = timed("04_nearby_pairs", lambda: find_nearby_pairs(segments, spatial_index, config))
    matches = timed("05_sspd", lambda: compare_sspd(pairs, segments, config.epsilon_m))
    clusters = timed("06_clusters", lambda: construct_candidate_clusters(segments, matches))
    extended = timed("07_extension", lambda: extend_clusters(clusters, metric, segments, pairs, config))
    selected = timed("08_selection", lambda: select_final_pathlets(extended, metric, config))
    validate_coverage(selected, metric)
    pathlets = timed("09_inverse_projection", lambda: convert_to_gps(selected, metric, projection))

    metrics: PipelineMetrics = {
        "trajectory_count": len(gps),
        "segment_count": len(segments),
        "zero_length_segment_count": sum(segment.start == segment.end for segment in segments),
        "spatial_candidate_pair_count": len(pairs),
        "sspd_match_count": len(matches),
        "candidate_cluster_count": len(clusters),
        "extended_pathlet_count": len(extended),
        "final_pathlet_count": len(pathlets),
        "shared_pathlet_count": sum(pathlet.count > 1 for pathlet in pathlets),
        "support_histogram": {
            str(count): sum(p.count == count for p in pathlets)
            for count in sorted({p.count for p in pathlets})
        },
        "coverage_complete": True,
        "epsilon_m": config.epsilon_m,
        "search_radius_m": config.radius_m,
        "approximate_search": config.approximate_search,
        "projection_max_radius_m": projection.max_radius_m,
        "step_runtime_ms": runtimes,
        "total_runtime_ms": (perf_counter() - started) * 1000,
    }
    result = ClusteringResult(pathlets, projection, metrics)
    artifacts_started = perf_counter()
    if config.output_dir is not None:
        write_json(
            config.output_dir / "pathlets.json",
            {
                "coordinate_order": "latitude,longitude",
                "config": config,
                "projection": projection,
                "trajectories": gps,
                "pathlets": pathlets,
            },
        )
    if config.debug:
        from .visualization import render_snapshot

        stage_data: tuple[object, ...] = (
            metric,
            segments,
            [{"segment_id": segment.segment_id, "bounds": segment.bounds} for segment in segments],
            pairs,
            matches,
            clusters,
            extended,
            selected,
            pathlets,
        )
        for step, (name, data) in enumerate(zip(STAGE_NAMES, stage_data, strict=True), 1):
            snapshot = config.debug_output_dir / f"{step:02d}_{name}.json"
            # Save every stage, even when only a subset of plots is requested.
            write_json(
                snapshot,
                {
                    "step": step,
                    "name": name,
                    "trajectories": metric,
                    "segments": segments,
                    "projection": projection,
                    "data": data,
                },
            )
            if step in config.debug_steps:
                render_snapshot(snapshot, sample_size=config.plot_sample_size)
        write_json(config.debug_output_dir / "metrics.json", metrics)
    metrics["artifact_runtime_ms"] = (perf_counter() - artifacts_started) * 1000
    if config.output_dir is not None:
        write_json(config.output_dir / "metrics.json", metrics)
    if config.debug:
        write_json(config.debug_output_dir / "metrics.json", metrics)
    LOGGER.info("counts: %s", {key: value for key, value in metrics.items() if key.endswith("_count")})
    return result


def main() -> None:
    """Parse CLI options and report malformed inputs with actionable errors."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--epsilon", type=float, default=100.0, help="SSPD threshold in projected meters")
    parser.add_argument("--search-radius", type=float)
    parser.add_argument("--approximate-search", action="store_true")
    parser.add_argument("--max-extension-steps", type=int, default=100)
    parser.add_argument("--extension-gap", type=float, help="maximum seed gap in meters; default 2 * epsilon")
    parser.add_argument("--min-pathlet-length", type=float, default=0.0)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/pathlets"))
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--debug-output-dir", type=Path, default=Path("debug/pathlets"))
    parser.add_argument("--debug-steps", default="1,2,3,4,5,6,7,8,9")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        config = ClusteringConfig(
            input_path=args.input,
            epsilon_m=args.epsilon,
            search_radius_m=args.search_radius,
            approximate_search=args.approximate_search,
            max_extension_steps=args.max_extension_steps,
            extension_gap_m=args.extension_gap,
            min_pathlet_length_m=args.min_pathlet_length,
            output_dir=args.output_dir,
            debug=args.debug,
            debug_output_dir=args.debug_output_dir,
            debug_steps=frozenset(int(value) for value in args.debug_steps.split(",") if value),
        )
        result = run_pipeline(config)
    except (ValueError, OSError) as error:
        parser.exit(2, f"pathlets: {error}\n")
    LOGGER.info("Saved %d pathlets to %s", len(result.pathlets), args.output_dir / "pathlets.json")
    LOGGER.info("Metrics: %s", result.metrics)


if __name__ == "__main__":
    main()
