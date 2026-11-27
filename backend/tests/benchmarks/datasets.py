"""Read and write trajectory-builder fixtures: one timestamped WGS84 point per CSV row."""

import csv
import hashlib
import os
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from itertools import groupby, islice
from operator import itemgetter
from pathlib import Path
from tempfile import NamedTemporaryFile

from models.similarity import ProjectedPoint, ProjectedSubtrajectory
from pyproj import Transformer
from pyproj.enums import TransformDirection
from trajectory_builder.schema import DATA_DIRECTORY, HEADER

DATA = DATA_DIRECTORY
LARGE_DATA = DATA.with_name("large_trajectories")
MAX_VERSIONED_BYTES = 100 * 1024**2
EPOCH = datetime(2000, 1, 1, tzinfo=UTC)
PORTO = (-8.61, 41.15)  # longitude, latitude of the benchmark generator's local metric frame
XY = list[tuple[float, float]]
Row = tuple[int, int, XY]


def in_ci() -> bool:
    """GitHub Actions sets CI=true; local runs can also use it to reproduce CI selection."""
    return os.getenv("CI", "").strip().lower() not in ("", "0", "false", "no")


def _fixture_dirs() -> tuple[Path, ...]:
    return (DATA,) if in_ci() else (DATA, LARGE_DATA)


def find_fixture(name: str) -> Path | None:
    """Resolve a fixture filename, preferring the committed copy over a local copy."""
    if Path(name).name != name:
        raise ValueError("Expected a filename, not a path")
    return next((file for directory in _fixture_dirs() if (file := directory / name).is_file()), None)


def builder_fixtures() -> list[Path]:
    """Discover named builder files once, leaving bench_* inputs to their explicit size cases."""
    by_name: dict[str, Path] = {}
    for directory in _fixture_dirs():
        for path in directory.glob("*.csv"):
            if not path.name.startswith("bench_") and path.is_file():
                by_name.setdefault(path.name, path)
    return [by_name[name] for name in sorted(by_name)]


def _check_ci_path(path: Path) -> None:
    if in_ci() and path.resolve().is_relative_to(LARGE_DATA):
        raise ValueError("large_trajectories is local-only")


def metric_frame(origin: tuple[float, float]) -> Transformer:
    """Create one WGS84-to-metres transform for a whole fixture, not one per route."""
    lon, lat = origin
    return Transformer.from_crs(
        "EPSG:4326", f"+proj=tmerc +lat_0={lat} +lon_0={lon} +k=1 +datum=WGS84 +units=m", always_xy=True
    )


def _coordinate(row: list[str]) -> tuple[float, float]:
    lon, lat = float(row[4]), float(row[5])
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        raise ValueError(f"Invalid WGS84 longitude/latitude: {lon}, {lat}")
    return lon, lat


def _csv_rows(lines: Iterable[str]):
    reader = csv.reader(lines)
    if next(reader, None) != list(HEADER):
        raise ValueError(f"Expected trajectory-builder CSV header: {','.join(HEADER)}")
    for row in reader:
        if len(row) != len(HEADER) or not row[0]:
            raise ValueError(f"Expected nine fields and a trajectory_id at CSV line {reader.line_num}")
        yield row


def fixture_counts(path: Path) -> tuple[int, int]:
    """Count complete paths and GPS points without holding a large custom CSV in RAM."""
    _check_ci_path(path)
    paths = points = 0
    last = None
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in _csv_rows(stream):
            if row[0] != last:
                paths += 1
                last = row[0]
            points += 1
    if not paths:
        raise ValueError(f"{path.name}: empty fixture")
    return paths, points


def fixture_origin(path: Path) -> tuple[float, float]:
    """Anchor a fixture's projection at its first point so all nested prefixes use the same frame."""
    _check_ci_path(path)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        first = next(_csv_rows(stream), None)
        if first is None:
            raise ValueError(f"{path.name}: empty fixture")
        return _coordinate(first)


def write_csv(path: Path, rows: Iterable[Row], *, origin: tuple[float, float] = PORTO) -> tuple[int, Path]:
    """Atomically export builder rows and return their count and actual storage location."""
    _check_ci_path(path)
    transform = metric_frame(origin)
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, prefix=".bench-", suffix=".tmp", delete=False) as tmp:
        pending = Path(tmp.name)
    try:
        with pending.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(HEADER)
            count = 0
            for path_id, trip_id, xy in rows:
                if len(xy) < 2:
                    raise ValueError(f"Path {path_id} has fewer than two points")
                xs, ys = zip(*xy, strict=True)
                lons, lats = transform.transform(xs, ys, direction=TransformDirection.INVERSE, errcheck=True)
                start = EPOCH.replace(tzinfo=None) + timedelta(seconds=2 * path_id)
                key = f"path_{path_id}"
                for step, (lon, lat) in enumerate(zip(lons, lats, strict=True)):
                    stamp = (start + timedelta(seconds=step)).isoformat(" ", timespec="seconds")
                    writer.writerow((key, 0, "UNKNOWN", stamp, f"{lon:.9f}", f"{lat:.9f}", "", "", trip_id))
                count += 1
            if not count:
                raise ValueError("No subpaths to write")
        if path.parent.resolve() == DATA and pending.stat().st_size >= MAX_VERSIONED_BYTES:
            if path.exists():
                raise FileExistsError(f"Oversized export would shadow {path}; choose a different --out name")
            path = LARGE_DATA / path.name
            _check_ci_path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
        pending.replace(path)
        return count, path
    finally:
        pending.unlink(missing_ok=True)


def load_prefix(
    path: Path, size: int | None = None, max_points: int | None = None
) -> tuple[list[ProjectedSubtrajectory], str]:
    """Load N complete route groups (or the entire file) and project before the clustering timer."""
    if size is not None and size < 1:
        raise ValueError("size must be positive")
    if max_points is not None and size is not None and 2 * size > max_points:
        raise ValueError(f"{size:,} subpaths exceed the point budget ({max_points:,})")
    transform = metric_frame(fixture_origin(path))
    digest = hashlib.sha256()
    paths = []
    seen: set[str] = set()
    point_count = 0
    with path.open(encoding="utf-8-sig", newline="") as stream:
        groups = groupby(_csv_rows(stream), key=itemgetter(0))
        for key, rows in islice(groups, size):
            if key in seen:
                raise ValueError(f"{path.name}: keep all rows for trajectory_id {key!r} together")
            seen.add(key)
            points = []
            db_id = None
            for row in rows:
                if db_id is not None and row[8] != db_id:
                    raise ValueError(f"{key}: database_trajectory_id changed within one route")
                db_id = row[8]
                point_count += 1
                if max_points is not None and point_count > max_points:
                    raise ValueError(f"Input exceeds {max_points:,} points")
                lon, lat = _coordinate(row)
                moment = datetime.fromisoformat(row[3])
                moment = moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment.astimezone(UTC)
                points.append((moment, lon, lat))
                digest.update(("\x1f".join(row) + "\n").encode())
            if len(points) < 2:
                raise ValueError(f"{key}: a subpath needs at least two GPS points")
            if db_id and not (db_id.isascii() and db_id.isdecimal()):
                raise ValueError(f"{key}: database_trajectory_id must be a non-negative integer or blank")
            # Missing optional IDs get distinct negative IDs, never colliding with a database trip ID.
            trip_id = int(db_id) if db_id else -len(seen)
            points.sort(key=itemgetter(0))
            times, lons, lats = zip(*points, strict=True)
            xs, ys = transform.transform(lons, lats, errcheck=True)
            projected = [ProjectedPoint(x, y) for x, y in zip(xs, ys, strict=True)]
            paths.append(ProjectedSubtrajectory(trip_id, times[0], times[-1], projected))
    if size is not None and len(paths) != size:
        raise ValueError(f"{path.name}: requested {size:,} subpaths but found only {len(paths):,}")
    return paths, digest.hexdigest()


def reference_band(digest: str, epsilon: float) -> tuple[int, int] | None:
    """Use an observed count range only for its exact input fingerprint and tolerance."""
    with Path(__file__).with_name("reference_bands.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["prefix_sha256"] == digest and float(row["epsilon_m"]) == epsilon:
                return int(row["min_clusters"]), int(row["max_clusters"])
    return None
