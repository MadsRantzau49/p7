"""Run the tolerance sweep alone with `pytest -m slow -k epsilon_sweep backend/tests/benchmarks`."""

import json
import os
import shutil
import statistics
import subprocess
import sys
from pathlib import Path

import pytest

from benchmarks.datasets import (
    DATA,
    LARGE_DATA,
    builder_fixtures,
    find_fixture,
    fixture_counts,
    in_ci,
    reference_band,
)
from benchmarks.prepare import PORTO_EXPORT, generate_csv

DEFAULT_EPSILON = 100
GIB = 1024**3


def _available_ram() -> int | None:
    """Read available Linux memory, including tighter limits imposed by a container."""
    info = Path("/proc/meminfo")
    if not info.is_file():
        return None
    available = next(
        (
            int(line.split()[1]) * 1024
            for line in info.read_text().splitlines()
            if line.startswith("MemAvailable:")
        ),
        None,
    )
    # A container may expose host-wide MemAvailable but have a much smaller cgroup allocation.
    root = Path("/sys/fs/cgroup")
    for line in Path("/proc/self/cgroup").read_text().splitlines():
        hierarchy, controllers, group = line.split(":", 2)
        if hierarchy == "0" and not controllers:
            mount, maximum, current = root, "memory.max", "memory.current"
        elif "memory" in controllers.split(","):
            mount, maximum, current = root / "memory", "memory.limit_in_bytes", "memory.usage_in_bytes"
        else:
            continue
        directory = mount / group.lstrip("/")
        for parent in (directory, *directory.parents):
            if parent != mount and mount not in parent.parents:
                break
            limit, used = parent / maximum, parent / current
            if limit.is_file() and used.is_file():
                value = limit.read_text().strip()
                if value.isdigit():
                    remaining = max(0, int(value) - int(used.read_text()))
                    available = remaining if available is None else min(available, remaining)
    return available


def _input(workload: str, size: int) -> Path:
    if workload == "porto":
        if size <= 1000:
            return DATA / "porto_sample.csv"
        export = find_fixture(PORTO_EXPORT.name)
        if export is None:
            pytest.fail(f"Missing committed fixture {PORTO_EXPORT.name}")
        return export

    if size >= 1_000_000:
        # Porto-jitter averages 22 points/path; spread has exactly three.
        needed = size * (12 if workload == "porto-jitter" else 4) * 1024
        _require_ram(f"{size:,} {workload} paths", needed)
    name = f"bench_{workload}-{size}.csv"
    if (existing := find_fixture(name)) is not None:
        return existing
    if in_ci():
        pytest.skip(f"{name} is not in the checkout; CI uses committed CSVs only")
    disk_bytes = size * (3072 if workload == "porto-jitter" else 384)
    if size >= 1_000_000 and shutil.disk_usage(DATA).free < disk_bytes:
        pytest.skip(f"Preparing {size:,} {workload} paths needs about {disk_bytes / GIB:.1f} GiB free disk")
    print(f"Preparing {name} (outside the timer)…", flush=True)
    _, path = generate_csv(DATA / name, workload, size, 42, DATA / "porto_sample.csv")
    return path


def _require_ram(label: str, needed: int) -> None:
    available = _available_ram()
    if available is None or available < needed:
        free = "unknown" if available is None else f"{available / GIB:.1f} GiB"
        pytest.skip(f"{label}: estimated {needed / GIB:.1f} GiB RAM; available: {free}")


def _duration(seconds: float) -> str:
    return f"{seconds * 1000:.3f} ms" if seconds < 1 else f"{seconds:.3f} s"


def _benchmark(
    path: Path,
    size: int | None,
    repeats: int,
    profile: bool = False,
    workload: str = "",
    *,
    epsilon: float = DEFAULT_EPSILON,
) -> None:
    max_points = max(3_000_000, (size or 0) * 30)
    if path.parent == LARGE_DATA and size is None:
        # An arbitrary builder file need not average <=30 points/path like the generated inputs.
        size, max_points = fixture_counts(path)
        _require_ram(path.name, 2048 * size + 512 * max_points)
    label = f"{size:,} paths" if size is not None else "all routes in fixture"
    print(f"\n{path.name} | {label} | ε={epsilon:g} m", flush=True)
    tests = DATA.parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(tests.parent / "src"), str(tests), env.get("PYTHONPATH", "")])
    times = []
    previous = None
    for mode in ["timing"] * repeats + (["profile"] if profile else []):
        # Keep process RSS per trial independent. IPC is internal; no benchmark report files.
        cmd = [
            sys.executable,
            "-m",
            "benchmarks.worker",
            str(path),
            str(size) if size is not None else "all",
            str(epsilon),
            str(max_points),
            mode,
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            timeout=180 if path.parent != LARGE_DATA and (size or 0) < 1_000_000 else None,
        )
        if result.returncode:
            pytest.fail(result.stderr.strip() or f"Clustering worker exited with code {result.returncode}")
        row = json.loads(result.stdout)
        band = reference_band(row["prefix_sha256"], epsilon)
        if band:
            assert band[0] <= row["clusters"] <= band[1], f"Expected {band}, got {row['clusters']} clusters"
        if epsilon == DEFAULT_EPSILON and workload in ("dense", "spread") and size is not None:
            assert row["clusters"] == (size if workload == "dense" else (size + 1) // 2)
        elif epsilon == DEFAULT_EPSILON and workload == "porto-jitter":
            # Variants of a single template are mutually within 100 m. Two cannot become representatives.
            assert 1 < row["clusters"] <= 1000
        observed = row["prefix_sha256"], row["clusters"]
        assert previous is None or previous == observed, "Input or cluster count changed between trials"
        previous = observed
        if mode == "timing":
            times.append(row["elapsed_s"])
            rss = "unavailable" if row["peak_rss_mib"] is None else f"{row['peak_rss_mib']:,.0f} MiB"
            print(
                f"  run {len(times)}/{repeats}: {_duration(row['elapsed_s'])} | {row['paths']:,} paths | "
                f"{row['points']:,} points | "
                f"{row['clusters']:,} clusters | peak RSS {rss}",
                flush=True,
            )
        else:
            cell = "skipped" if row["grid_cell_m"] is None else f"{row['grid_cell_m']:g} m cells"
            print(
                f"  grid: {_duration(row['grid_s'])} ({cell}, {row['path_cell_pairs']:,} path-cell pairs) | "
                f"assign: {_duration(row['assign_s'])}, {row['candidate_checks']:,} candidate checks, "
                f"{row['frechet_runs']:,} Fréchet runs",
                flush=True,
            )
    if repeats > 1:
        print(f"  median: {_duration(statistics.median(times))}", flush=True)


@pytest.mark.slow
@pytest.mark.parametrize("epsilon", [0, 1, 5.5, 100, 10_000], ids=lambda value: f"{value:g}m")
@pytest.mark.parametrize(
    ("filename", "size"),
    [pytest.param("tiny.csv", 5, id="tiny-5"), pytest.param("porto_sample.csv", 250, id="porto-250")],
)
def test_epsilon_sweep(filename, size, epsilon, capsys):
    """Vary only tolerance on fixed CSV prefixes, from exact matching to a 10 km leash."""
    with capsys.disabled():
        _benchmark(DATA / filename, size, repeats=3, profile=True, epsilon=epsilon)


@pytest.mark.slow
@pytest.mark.parametrize(
    ("workload", "size"),
    [
        ("porto", 1000),
        ("porto", 10_000),
        ("porto", 36_466),
        ("porto-jitter", 1000),
        ("porto-jitter", 10_000),
        ("porto-jitter", 100_000),
        ("spread", 250),
        ("spread", 500),
        ("spread", 1000),
        ("spread", 100_000),
        ("dense", 250),
        ("dense", 500),
        ("dense", 1000),
    ],
)
def test_clustering_scale(workload, size, capsys):
    """Standard size sweep, three independent timings plus one diagnostic run per size."""
    with capsys.disabled():  # Show normal print output even without pytest -s.
        _benchmark(_input(workload, size), size, repeats=3, profile=True, workload=workload)


@pytest.mark.extra_test
@pytest.mark.parametrize(
    ("workload", "size"),
    [
        pytest.param("spread", 1_000_000, id="spread-1M"),
        pytest.param("porto-jitter", 1_000_000, id="porto-1M"),
        pytest.param("porto-jitter", 10_000_000, id="porto-10M"),
        pytest.param("porto-jitter", 100_000_000, id="porto-100M"),
    ],
)
def test_large_clustering(workload, size, capsys):
    """One full, uninstrumented clustering pass on the selected number of subpaths."""
    with capsys.disabled():
        _benchmark(_input(workload, size), size, repeats=1, workload=workload)


@pytest.mark.parametrize(
    "fixture",
    [
        pytest.param(
            p, id=p.stem, marks=pytest.mark.extra_test if p.parent == LARGE_DATA else pytest.mark.slow
        )
        for p in builder_fixtures()
    ],
)
def test_builder_fixture(fixture, capsys):
    """Exercise builder fixtures; local-only files require the extra_test marker."""
    with capsys.disabled():
        _benchmark(fixture, None, repeats=1)
