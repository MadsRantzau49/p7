import csv
from datetime import UTC, datetime, timedelta

import pytest
from helpers.similarity_steps.route_clustering.clustering import cluster_routes
from trajectory_builder import server
from trajectory_builder.schema import HEADER

from benchmarks import datasets
from benchmarks.datasets import DATA, EPOCH, load_prefix, reference_band
from benchmarks.prepare import generate_csv
from benchmarks.worker import validate_members


def test_short_paths_have_known_members_and_distinct_trip_counts():
    """Straight paths, detours with the same endpoints, and the reverse direction are separate."""
    paths, _ = load_prefix(DATA / "tiny.csv", 6)
    routes = cluster_routes(paths, epsilon=100)
    validate_members(paths, routes)
    # Recover path IDs, not trip IDs: paths 1 and 2 are separate subpaths of trip 1.
    groups = {
        frozenset((m.exit_a_time - EPOCH) // timedelta(seconds=2) for m in r.members): r.count for r in routes
    }
    assert groups == {frozenset([1, 2, 3]): 2, frozenset([4, 5]): 2, frozenset([6]): 1}


@pytest.mark.parametrize("size", [100, 1000])
def test_real_porto_geometry_stays_in_reference_band(size):
    """Check observed ranges on real data without freezing the exact representative choices."""
    paths, digest = load_prefix(DATA / "porto_sample.csv", size)
    routes = cluster_routes(paths, epsilon=100)
    validate_members(paths, routes)
    band = reference_band(digest, 100)
    assert band is not None, "Porto fixture changed; review the new geometry before updating its reference"
    assert band[0] <= len(routes) <= band[1]


@pytest.mark.parametrize(("workload", "expected"), [("spread", 4), ("dense", 8), ("porto-jitter", 3)])
def test_generated_workloads_are_nested_and_exercise_different_cases(tmp_path, workload, expected):
    """Larger generated CSVs preserve the short prefixes and the intended cluster geometry."""
    base = DATA / "tiny.csv"
    output = tmp_path / "long.csv"
    n = 8 if workload != "porto-jitter" else 50
    generate_csv(output, workload, n, 42, base)
    paths, fingerprint = load_prefix(output, n)
    routes = cluster_routes(paths, 100)
    validate_members(paths, routes)
    assert len(routes) == expected
    generate_csv(output, workload, n + 5, 42, base)
    assert load_prefix(output, n)[1] == fingerprint


def test_map_export_can_be_clustered_directly(tmp_path, monkeypatch):
    """Anonymous map routes keep separate identities; times order the GPS vertices before projection."""
    monkeypatch.setattr(server, "DATA_DIRECTORY", tmp_path)
    text = (
        ",".join(HEADER) + "\n"
        "home_a,7,CAR,2026-01-01 10:00:30,9.921,57.03,Aalborg,,\n"
        "home_a,7,CAR,2026-01-01 10:00:00,9.911,57.03,Aalborg,,\n"
        "home_b,7,CAR,2026-01-01 10:00:00,9.911,57.0301,Aalborg,,0\n"
        "home_b,7,CAR,2026-01-01 10:00:30,9.921,57.0301,Aalborg,,0\n"
    )
    path = server.save_fixture(server.fixture_name_from_csv(text), text)
    assert path.name == "home_a.csv"
    paths, _ = load_prefix(path)
    assert {p.trajectory_id for p in paths} == {-1, 0}
    assert paths[0].exit_a_time == datetime(2026, 1, 1, 10, tzinfo=UTC)
    a, b = paths[0].projected_points
    assert 590 < b.x - a.x < 620  # 0.01 degrees longitude at 57°N, in metres
    [cluster] = cluster_routes(paths, epsilon=100)
    assert cluster.count == 2


def test_new_templates_stay_in_their_own_city(tmp_path):
    """A generator using the builder's Danish template must not move it to Porto."""
    output = tmp_path / "my_variations.csv"
    generate_csv(output, "porto-jitter", 3, 42, DATA / "template.csv")
    with output.open(newline="") as stream:
        reader = csv.DictReader(stream)
        assert reader.fieldnames == list(HEADER)
        points = list(reader)
    assert len(points) == 15
    assert all(9.89 < float(p["longitude"]) < 9.93 and 57.02 < float(p["latitude"]) < 57.05 for p in points)
    paths, _ = load_prefix(output)
    assert len(paths) == 3


def test_size_guards_refuse_incomplete_or_oversized_inputs():
    """Never silently substitute a smaller sample for the requested measurement."""
    with pytest.raises(ValueError, match="found only 6"):
        load_prefix(DATA / "tiny.csv", 7)
    with pytest.raises(ValueError, match="exceeds 12 points"):
        load_prefix(DATA / "tiny.csv", 6, max_points=12)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("bench_porto.csv", None),
        ("bench_porto-jitter-1000.csv", None),
        ("bench_spread-250.csv", 2),
        ("bench_dense-250.csv", 4),
    ],
)
def test_shared_workloads_are_ready_in_a_clean_checkout(name, expected):
    """CI clusters four paths from each shared workload without generating or downloading any CSVs."""
    paths, _ = load_prefix(DATA / name, 4)
    routes = cluster_routes(paths, 100)
    validate_members(paths, routes)
    if expected is not None:
        assert len(routes) == expected


def test_oversized_files_are_usable_locally_and_invisible_to_ci(tmp_path, monkeypatch):
    """Exercise the actual size boundary, both lookup paths and CI's exclusion using a small export."""
    shared = tmp_path / "trajectories"
    local = tmp_path / "large_trajectories"
    monkeypatch.setattr(datasets, "DATA", shared)
    monkeypatch.setattr(datasets, "LARGE_DATA", local)
    monkeypatch.delenv("CI", raising=False)
    rows = [(1, 1, [(0.0, 0.0), (100.0, 0.0)])]

    _, small = datasets.write_csv(shared / "example.csv", rows)
    monkeypatch.setattr(datasets, "MAX_VERSIONED_BYTES", small.stat().st_size)
    count, big = datasets.write_csv(shared / "detour.csv", rows)
    assert count == 1 and big == local / "detour.csv"
    assert not (shared / big.name).exists()
    assert datasets.find_fixture(big.name) == big
    assert datasets.builder_fixtures() == [big, small]
    assert datasets.fixture_counts(big) == (1, 2)
    assert len(load_prefix(big)[0]) == 1
    # If someone has a second copy, the versioned source wins.
    (local / small.name).write_bytes(small.read_bytes())
    assert datasets.find_fixture(small.name) == small

    monkeypatch.setenv("CI", "true")
    assert datasets.find_fixture(big.name) is None
    assert datasets.builder_fixtures() == [small]
    with pytest.raises(ValueError, match="local-only"):
        load_prefix(big)
    with pytest.raises(ValueError, match="local-only"):
        datasets.write_csv(shared / "too_big.csv", rows)
    assert not (local / "too_big.csv").exists()
