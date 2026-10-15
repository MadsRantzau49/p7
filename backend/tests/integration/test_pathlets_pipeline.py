"""Full file-to-Leaflet pipeline checks, including complete source interval coverage."""

import json
import os
import subprocess
import sys
from collections import defaultdict
from dataclasses import replace
from pathlib import Path

import pytest
from pathlets.geometry import convert_to_meters, interval_coordinates, length, sspd
from pathlets.loading import load_trajectories
from pathlets.main import run_pipeline
from pathlets.models import Assignment, ClusteringConfig

FIXTURE = Path(__file__).parents[1] / "data/trajectories/aalborg_germany.csv"
ROOT = Path(__file__).parents[3]


@pytest.mark.parametrize("epsilon", [100.0, 2000.0])
def test_aalborg_pipeline_coverage_geometry_and_determinism(tmp_path, epsilon):
    """Every source interval survives, each contributor passes SSPD, and runs agree."""
    config = ClusteringConfig(FIXTURE, epsilon_m=epsilon, output_dir=tmp_path / "result")
    first = run_pipeline(config)
    second = run_pipeline(replace(config, output_dir=tmp_path / "repeat"))
    assert first.pathlets == second.pathlets
    assert first.metrics["coverage_complete"] is True
    assert first.metrics["trajectory_count"] == 8
    assert first.metrics["segment_count"] == 190
    assert first.metrics["zero_length_segment_count"] == 1
    assert first.metrics["spatial_candidate_pair_count"] < 190 * 189 // 2
    assert len(first.metrics["step_runtime_ms"]) == 10

    source = load_trajectories(FIXTURE)
    metric, _ = convert_to_meters(source)
    by_id = {trajectory.trajectory_id: trajectory for trajectory in metric}
    coverage: dict[str, list[tuple[float, float]]] = defaultdict(list)
    shared_meters = 0.0
    for pathlet in first.pathlets:
        assert pathlet.count == len(pathlet.trajectory_ids) == len(pathlet.assignments)
        assert pathlet.count == len(set(pathlet.trajectory_ids))
        assert pathlet.max_sspd_m <= epsilon
        representative = interval_coordinates(
            by_id[pathlet.representative.trajectory_id], pathlet.representative
        )
        if pathlet.count > 1:
            shared_meters += length(representative)
        for assignment in pathlet.assignments:
            coverage[assignment.trajectory_id].append((assignment.start, assignment.end))
            interval = Assignment(assignment.trajectory_id, assignment.start, assignment.end)
            assert (
                sspd(representative, interval_coordinates(by_id[interval.trajectory_id], interval)) <= epsilon
            )
            assert assignment.source_rows
            assert assignment.start_timestamp is not None
            assert assignment.end_timestamp is not None
            assert assignment.start_timestamp <= assignment.end_timestamp
        assert all(54 < lat < 58 and 7 < lon < 11 for lat, lon in pathlet.coordinates)
    assert set(coverage) == set(by_id)
    for trajectory_id, intervals in coverage.items():
        cursor = 0
        for start, end in sorted(intervals):
            assert start == pytest.approx(cursor, abs=1e-9)
            assert end > start
            cursor = end
        assert cursor == len(by_id[trajectory_id].coordinates) - 1
    assert shared_meters > 0
    assert any(p.count == 1 for p in first.pathlets)
    if epsilon == 2000:
        assert max(p.count for p in first.pathlets) >= 3
        assert shared_meters > 100_000  # Substantial corridors, not just crossing points.
    assert config.output_dir is not None
    payload = json.loads((config.output_dir / "pathlets.json").read_text())
    assert payload["coordinate_order"] == "latitude,longitude"
    assert len(payload["pathlets"]) == len(first.pathlets)
    metrics = json.loads((config.output_dir / "metrics.json").read_text())
    assert metrics["total_runtime_ms"] > 0
    assert not config.debug


@pytest.mark.parametrize("epsilon", [0.0, 100.0, 2000.0])
def test_no_index_pipeline_preserves_outputs_and_never_builds_a_tree(monkeypatch, epsilon):
    """Only discovery changes: matches, assignments, geometry, and coverage remain identical."""
    from pathlets import main as pipeline

    config = ClusteringConfig(FIXTURE, epsilon_m=epsilon, output_dir=None)
    indexed = run_pipeline(config)

    def forbidden(*args, **kwargs):
        raise AssertionError("no-index mode must not build or query an STRtree")

    monkeypatch.setattr(pipeline, "build_spatial_index", forbidden)
    monkeypatch.setattr(pipeline, "find_nearby_pairs", forbidden)
    baseline = run_pipeline(replace(config, use_spatial_index=False))
    assert indexed.pathlets == baseline.pathlets
    assert indexed.projection == baseline.projection
    for field in (
        "spatial_candidate_pair_count",
        "sspd_match_count",
        "candidate_cluster_count",
        "extended_pathlet_count",
        "final_pathlet_count",
        "coverage_complete",
        "possible_cross_trajectory_pair_count",
    ):
        assert indexed.metrics[field] == baseline.metrics[field]
    assert indexed.metrics["use_spatial_index"] is True
    assert indexed.metrics["candidate_search_method"] == "strtree"
    assert baseline.metrics["use_spatial_index"] is False
    assert baseline.metrics["candidate_search_method"] == "brute_force"
    assert baseline.metrics["step_runtime_ms"]["03_spatial_index"] == 0
    assert (
        baseline.metrics["candidate_discovery_runtime_ms"]
        == baseline.metrics["step_runtime_ms"]["04_nearby_pairs"]
    )
    assert indexed.metrics["candidate_discovery_runtime_ms"] == (
        indexed.metrics["step_runtime_ms"]["03_spatial_index"]
        + indexed.metrics["step_runtime_ms"]["04_nearby_pairs"]
    )
    assert (
        baseline.metrics["spatial_candidate_pair_count"]
        < baseline.metrics["possible_cross_trajectory_pair_count"]
    )


@pytest.mark.parametrize("epsilon", [0.0, 100.0, 2000.0])
@pytest.mark.parametrize("indexed", [False, True])
def test_unfiltered_pipeline_compares_every_pair_without_changing_results(monkeypatch, epsilon, indexed):
    """All cross-source pairs actually reach SSPD with filtering disabled in either index mode."""
    from pathlets import spatial

    config = ClusteringConfig(FIXTURE, epsilon_m=epsilon, use_spatial_index=indexed, output_dir=None)
    filtered = run_pipeline(config)
    original_sspd = spatial.sspd
    calls = 0

    def counted_sspd(first, second):
        nonlocal calls
        calls += 1
        return original_sspd(first, second)

    monkeypatch.setattr(spatial, "sspd", counted_sspd)
    unfiltered = run_pipeline(replace(config, use_bounding_box_filter=False))
    assert unfiltered.pathlets == filtered.pathlets
    assert unfiltered.metrics["coverage_complete"] is True
    assert unfiltered.metrics["use_spatial_index"] is indexed
    assert unfiltered.metrics["use_bounding_box_filter"] is False
    assert calls == unfiltered.metrics["sspd_comparison_count"]
    assert calls == unfiltered.metrics["possible_cross_trajectory_pair_count"]
    assert calls == unfiltered.metrics["spatial_candidate_pair_count"]
    assert calls > filtered.metrics["sspd_comparison_count"]
    assert unfiltered.metrics["sspd_match_count"] == filtered.metrics["sspd_match_count"]


def test_every_debug_stage_and_independent_saved_render(tmp_path):
    """Rendering all nine stages changes no pathlets and retains complete stage data."""
    from pathlets.visualization import render_snapshot

    config = ClusteringConfig(
        FIXTURE,
        epsilon_m=2000,
        output_dir=tmp_path / "out",
        debug=True,
        debug_output_dir=tmp_path / "debug",
        plot_sample_size=5,
    )
    debug = run_pipeline(config)
    plain = run_pipeline(replace(config, debug=False, output_dir=tmp_path / "plain"))
    assert debug.pathlets == plain.pathlets
    assert len(list(config.debug_output_dir.glob("*.png"))) == 8
    assert len(list(config.debug_output_dir.glob("*.html"))) == 1
    snapshots = sorted(p for p in config.debug_output_dir.glob("[0-9][0-9]_*.json"))
    assert len(snapshots) == 9
    nearby = json.loads(snapshots[3].read_text())
    assert len(nearby["data"]) == debug.metrics["spatial_candidate_pair_count"]
    assert len(nearby["data"]) > config.plot_sample_size
    standalone = tmp_path / "standalone.png"
    assert render_snapshot(snapshots[4], standalone, sample_size=3) == standalone
    assert standalone.stat().st_size > 1000
    html = (config.debug_output_dir / "09_final_gps_pathlets.html").read_text()
    assert "L.polyline" in html
    assert "SSPD pathlets" in html


def test_selected_debug_steps_still_save_all_intermediates(tmp_path):
    """Plot selection is independent of saving full numerical stage outputs."""
    config = ClusteringConfig(
        FIXTURE,
        output_dir=tmp_path / "out",
        debug=True,
        debug_output_dir=tmp_path / "debug",
        debug_steps=frozenset({6}),
    )
    run_pipeline(config)
    assert len(list(config.debug_output_dir.glob("*.png"))) == 1
    assert len(list(config.debug_output_dir.glob("[0-9][0-9]_*.json"))) == 9


def test_cli_headless_execution_and_malformed_input(tmp_path):
    """The module CLI has useful output and exits cleanly for invalid CSV inputs."""
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "backend/src")}
    command = [
        sys.executable,
        "-m",
        "pathlets.main",
        "--input",
        str(FIXTURE),
        "--output-dir",
        str(tmp_path / "out"),
    ]
    completed = subprocess.run(command, cwd=ROOT, env=environment, text=True, capture_output=True)
    assert completed.returncode == 0, completed.stderr
    assert "07_extension:" in completed.stderr
    assert (tmp_path / "out/metrics.json").is_file()
    baseline = subprocess.run(
        [*command, "--no-spatial-index"], cwd=ROOT, env=environment, text=True, capture_output=True
    )
    assert baseline.returncode == 0, baseline.stderr
    assert "03_spatial_index: skipped" in baseline.stderr
    baseline_metrics = json.loads((tmp_path / "out/metrics.json").read_text())
    assert baseline_metrics["use_spatial_index"] is False
    assert baseline_metrics["step_runtime_ms"]["03_spatial_index"] == 0
    unfiltered = subprocess.run(
        [*command, "--no-bounding-box-filter"], cwd=ROOT, env=environment, text=True, capture_output=True
    )
    assert unfiltered.returncode == 0, unfiltered.stderr
    unfiltered_metrics = json.loads((tmp_path / "out/metrics.json").read_text())
    assert unfiltered_metrics["use_spatial_index"] is True
    assert unfiltered_metrics["use_bounding_box_filter"] is False
    assert (
        unfiltered_metrics["sspd_comparison_count"]
        == unfiltered_metrics["possible_cross_trajectory_pair_count"]
    )

    # A separate interpreter proves non-debug execution does not import plotting.
    code = (
        "import sys; from pathlib import Path; from pathlets.main import run_pipeline; "
        "from pathlets.models import ClusteringConfig; "
        f"run_pipeline(ClusteringConfig(Path({str(FIXTURE)!r}),"
        f"output_dir=Path({str(tmp_path / 'headless')!r})));"
        "assert 'matplotlib' not in sys.modules; assert 'pathlets.visualization' not in sys.modules"
    )
    headless = subprocess.run(
        [sys.executable, "-c", code], env=environment, cwd=ROOT, text=True, capture_output=True
    )
    assert headless.returncode == 0, headless.stderr
    malformed = tmp_path / "bad.csv"
    malformed.write_text("wrong,header\n1,2\n")
    failed = subprocess.run(
        [*command[:3], "--input", str(malformed)], env=environment, cwd=ROOT, text=True, capture_output=True
    )
    assert failed.returncode == 2
    assert "line 1" in failed.stderr
    assert "Traceback" not in failed.stderr
