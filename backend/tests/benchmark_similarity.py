"""Measure continuous pathlet runtime and quality, with optional independent verification."""

import argparse
import json
import math
from array import array
from collections import Counter
from pathlib import Path
from statistics import median
from time import perf_counter

from helpers.trajectory_csv_parser import parse_trajectory_csv
from models.subtrajectory import Subtrajectory
from services.similarity_service import SimilarityService


def benchmark(path: Path, epsilon: float, verify: bool) -> dict:
    """Time the pipeline separately from CSV parsing, statistics and geometry verification."""
    load_start = perf_counter()
    with path.open(encoding="utf-8-sig", newline="") as fixture:
        routes = parse_trajectory_csv(fixture)
    next_id = max((route.trajectory_id or 0 for route in routes), default=0) + 1
    inputs = []
    for index, route in enumerate(routes):
        trajectory_id = route.trajectory_id
        if trajectory_id is None:
            trajectory_id = next_id
            next_id += 1
        inputs.append(Subtrajectory(
            index, trajectory_id,
            route.points[0].point_timestamp, route.points[-1].point_timestamp, route.points,
        ))
    load_seconds = perf_counter() - load_start

    service = SimilarityService()
    start = perf_counter()
    projected = service.projection(inputs)
    projection_end = perf_counter()
    pathlets = service.extend_pathlets(projected, epsilon)
    extension_end = perf_counter()
    service.inverse_projection(pathlets)
    end = perf_counter()

    lengths = []
    for trajectory in projected:
        offsets = array("d", [0.0])
        for a, b in zip(trajectory.projected_points, trajectory.projected_points[1:], strict=False):
            offsets.append(offsets[-1] + math.hypot(b.x - a.x, b.y - a.y))
        lengths.append(offsets)
    total_length = sum(offsets[-1] for offsets in lengths)
    extended_length = 0.0
    distribution = Counter()
    for pathlet in pathlets:
        segment_count = pathlet.representative.end_index - pathlet.representative.start_index
        distribution[segment_count] += 1
        if segment_count > 1:
            extended_length += sum(
                lengths[section.section_index][section.end_index]
                - lengths[section.section_index][section.start_index]
                for section in pathlet.sections
            )
    result = {
        "fixture": path.name,
        "points": sum(len(trajectory.points) for trajectory in inputs),
        "csv_load_seconds": round(load_seconds, 3),
        "pipeline_seconds": round(end - start, 3),
        "projection_seconds": round(projection_end - start, 3),
        "extension_seconds": round(extension_end - projection_end, 3),
        "inverse_seconds": round(end - extension_end, 3),
        "pathlets": len(pathlets),
        "single_segment_pathlets": distribution[1],
        "median_segments": median(
            pathlet.representative.end_index - pathlet.representative.start_index for pathlet in pathlets
        ),
        "max_segments": max(distribution),
        "max_length_m": round(max(pathlet.representative.representative_end_m for pathlet in pathlets), 2),
        "input_distance_on_extended_pathlets_percent": (
            round(100 * extended_length / total_length, 2) if total_length else 100.0
        ),
        "support_intervals": sum(len(pathlet.support) for pathlet in pathlets),
    }
    if verify:
        from shapely.geometry import LineString, Point
        from shapely.ops import substring

        coverage = [bytearray(len(trajectory.projected_points) - 1) for trajectory in projected]
        maximum_distance = 0.0
        for pathlet in pathlets:
            coordinates = [(point.x, point.y) for point in pathlet.representative.points]
            representative = LineString(coordinates) if len(coordinates) > 1 else Point(coordinates[0])
            assert pathlet.count == len({section.trajectory_id for section in pathlet.sections})
            for section in pathlet.sections:
                covered = coverage[section.section_index]
                assert not any(covered[section.start_index : section.end_index]), "Duplicate assignment"
                covered[section.start_index : section.end_index] = (
                    b"\x01" * (section.end_index - section.start_index)
                )
                reference_interval = (
                    substring(representative, section.representative_start_m, section.representative_end_m)
                    if isinstance(representative, LineString) and representative.length else representative
                )
                coordinates = [(point.x, point.y) for point in section.points]
                member = LineString(coordinates) if len(coordinates) > 1 else Point(coordinates[0])
                maximum_distance = max(maximum_distance, reference_interval.hausdorff_distance(member))
        assert all(all(covered) for covered in coverage), "Missing input segments"
        assert maximum_distance <= epsilon + 1e-6, maximum_distance
        result["verified_segments"] = sum(len(covered) for covered in coverage)
        result["max_symmetric_interval_distance_m"] = round(maximum_distance, 6)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, nargs="+", help="Trajectory CSV fixtures")
    parser.add_argument("--epsilon", type=float, default=100)
    parser.add_argument("--verify", action="store_true", help="Check exact coverage and interval distances")
    arguments = parser.parse_args()
    if not math.isfinite(arguments.epsilon) or arguments.epsilon < 0:
        parser.error("epsilon must be finite and non-negative")
    for fixture_path in arguments.input:
        print(json.dumps(benchmark(fixture_path, arguments.epsilon, arguments.verify)), flush=True)
