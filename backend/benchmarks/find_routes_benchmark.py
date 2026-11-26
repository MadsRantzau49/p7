"""Benchmark the find-routes pipeline (extraction + clustering) against a real database.

Runs the /api/subtrajectories/get handler in-process for a fixed set of searches and collects the
step timings that the services already log ("<step> took <n> seconds"). Each result also gets a
fingerprint of the routes (counts, members and representative points), so two code versions can be
checked for identical output.

The connection settings come from the DATABASE_* environment variables. Unset ones default to an
SSH tunnel on localhost:15432 (database p7, user postgres). The password is left to libpq (~/.pgpass).

Example, comparing two checkouts:
    python backend/benchmarks/find_routes_benchmark.py --src backend/src --runs 3 --out after.json
    python backend/benchmarks/find_routes_benchmark.py --src /path/to/old/backend/src --out before.json
    python backend/benchmarks/find_routes_benchmark.py --compare before.json after.json
"""

import argparse
import hashlib
import json
import logging
import os
import re
import resource
import sys
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from statistics import median

CASES: dict[str, dict] = {
    # São Bento station to Campanhã station, 0.001 degree boxes.
    "saobento_campanha_month": {
        "a": (-8.6115, 41.1445, -8.6095, 41.1465),
        "b": (-8.5865, 41.1478, -8.5845, 41.1498),
        "dates": ("2013-07-01", "2013-07-31"),
    },
    "saobento_campanha_year": {
        "a": (-8.6115, 41.1445, -8.6095, 41.1465),
        "b": (-8.5865, 41.1478, -8.5845, 41.1498),
        "dates": ("2013-07-01", "2014-06-30"),
    },
    "saobento_campanha_year_eps250": {
        "a": (-8.6115, 41.1445, -8.6095, 41.1465),
        "b": (-8.5865, 41.1478, -8.5845, 41.1498),
        "dates": ("2013-07-01", "2014-06-30"),
        "epsilon": 250.0,
    },
    # Two 100 m boxes 300 m apart in the busy centre (index benchmark case 2).
    "centre_month": {
        "a": (-8.611597, 41.14805, -8.610403, 41.14895),
        "b": (-8.607576, 41.148153, -8.606382, 41.149053),
        "dates": ("2013-10-01", "2013-10-31"),
    },
    # Campanhã to São João hospital (index benchmark case 4), whole year.
    "campanha_saojoao_year": {
        "a": (-8.585897, 41.14835, -8.584703, 41.14925),
        "b": (-8.601597, 41.18125, -8.600403, 41.18215),
        "dates": ("2013-07-01", "2014-06-30"),
    },
    # Beijing Railway Station to Beijing West, 250 m boxes, the whole Beijing week.
    "beijing_stations_all": {
        "a": (116.424069, 39.900752, 116.429931, 39.905248),
        "b": (116.31907, 39.892752, 116.32493, 39.897248),
        "dates": ("2008-02-01", "2008-02-09"),
    },
}

PORTO_YEAR = ("2013-07-01", "2014-06-30")


def _square(longitude: float, latitude: float, half_metres: float) -> tuple[float, float, float, float]:
    """A box half_metres to each side of a point in Porto (1 degree is about 83.8 by 111 km there)."""
    half_lon, half_lat = half_metres / 83_800, half_metres / 111_000
    return (longitude - half_lon, latitude - half_lat, longitude + half_lon, latitude + half_lat)


# Large areas over the whole Porto year, to push as much data through as possible. They take
# minutes with older code, so they only run when named with --cases or selected with --large.
# Downtown (around São Bento and Aliados) to Boavista, the two busiest areas, growing boxes.
for _half in (250, 500, 1000):
    CASES[f"porto_downtown_boavista_{_half}m"] = {
        "a": _square(-8.610, 41.146, _half),
        "b": _square(-8.640, 41.160, _half),
        "dates": PORTO_YEAR,
        "large": True,
    }
# Near worst case: about 3 x 2.4 km of downtown to 3.7 x 3.3 km of the west, 330 m apart.
CASES["porto_worst"] = {
    "a": (-8.632, 41.135, -8.596, 41.157),
    "b": (-8.680, 41.150, -8.636, 41.180),
    "dates": PORTO_YEAR,
    "large": True,
}
DEFAULT_CASES = [name for name, case in CASES.items() if not case.get("large")]
LARGE_CASES = [name for name, case in CASES.items() if case.get("large")]

STEP_PATTERN = re.compile(r"^(?P<step>.+) took (?P<seconds>[0-9.]+) seconds$")


class StepCollector(logging.Handler):
    """Keep every "<step> took <n> seconds" record, plus the other INFO lines for reference."""

    def __init__(self) -> None:
        super().__init__(logging.INFO)
        self.steps: list[tuple[str, str, float]] = []
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        """Store one log record."""
        message = record.getMessage()
        match = STEP_PATTERN.match(message)
        if match:
            self.steps.append((record.name, match["step"], float(match["seconds"])))
        else:
            self.lines.append(f"{record.name}: {message}")


@dataclass
class RunResult:
    seconds: float
    serialise_seconds: float
    routes: int
    subtrajectories: int
    fingerprint: str
    steps: dict[str, float]
    peak_rss_mb: float


def fingerprint(routes: list) -> tuple[str, int]:
    """Hash counts, members and representative points (rounded to about 1 cm)."""
    digest = hashlib.sha256()
    members = 0
    for route in routes:
        digest.update(f"{route.count}|".encode())
        for member in route.members:
            members += 1
            digest.update(
                f"{member.trajectory_id},{member.exit_a_time.isoformat()},{member.entry_b_time.isoformat()};".encode()
            )
        for point in route.points:
            digest.update(f"{point.latitude:.7f},{point.longitude:.7f};".encode())
        digest.update(b"\n")
    return digest.hexdigest()[:16], members


def run_benchmarks(src: Path, case_names: list[str], runs: int) -> dict:
    """Run every case `runs` times and return the raw results."""
    os.environ.setdefault("DATABASE_HOST", "localhost")
    os.environ.setdefault("DATABASE_PORT", "15432")
    os.environ.setdefault("DATABASE_NAME", "p7")
    os.environ.setdefault("DATABASE_USER", "postgres")
    sys.path.insert(0, str(src.resolve()))

    collector = StepCollector()
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger().addHandler(collector)
    logging.getLogger().setLevel(logging.INFO)
    for handler in logging.getLogger().handlers:
        if handler is not collector:
            handler.setLevel(logging.WARNING)

    from database.connection import create_db_connection
    from database.repositories.trajectory_repository import TrajectoryRepository
    from dependencies import get_route_clustering_service, get_subtrajectory_service
    from models.date_range import DateRange
    from models.similarity import Route
    from pydantic import TypeAdapter
    from routers.router import get_subtrajectories

    adapter = TypeAdapter(list[Route])
    results: dict[str, list[dict]] = {}
    for name in case_names:
        case = CASES[name]
        results[name] = []
        for run in range(1, runs + 1):
            collector.steps.clear()
            collector.lines.clear()
            start = time.perf_counter()
            with create_db_connection() as connection:
                routes = get_subtrajectories(
                    # The app's own wiring, so the services are configured as in a request.
                    subtrajectory_service=get_subtrajectory_service(TrajectoryRepository(connection)),
                    route_clustering_service=get_route_clustering_service(),
                    dates=DateRange(
                        date.fromisoformat(case["dates"][0]), date.fromisoformat(case["dates"][1])
                    ),
                    a_longitude=case["a"][0],
                    a_latitude=case["a"][1],
                    a_max_longitude=case["a"][2],
                    a_max_latitude=case["a"][3],
                    b_longitude=case["b"][0],
                    b_latitude=case["b"][1],
                    b_max_longitude=case["b"][2],
                    b_max_latitude=case["b"][3],
                    epsilon=case.get("epsilon", 100.0),
                )
                routes = routes or []
            serialise_start = time.perf_counter()
            adapter.dump_json(routes)
            end = time.perf_counter()

            route_hash, members = fingerprint(routes)
            steps: dict[str, float] = {}
            for logger_name, step, seconds in collector.steps:
                steps[f"{logger_name}: {step}"] = steps.get(f"{logger_name}: {step}", 0.0) + seconds
            peak_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # Process peak so far.
            result = RunResult(
                end - start, end - serialise_start, len(routes), members, route_hash, steps, peak_mb
            )
            results[name].append(result.__dict__ | {"log": list(collector.lines)})
            print(
                f"{name} run {run}: {result.seconds:7.2f} s, routes={result.routes}, "
                f"subtrajectories={result.subtrajectories}, fingerprint={result.fingerprint}, "
                f"peak memory={result.peak_rss_mb:,.0f} MB",
                flush=True,
            )
    return {"src": str(src), "runs": runs, "results": results}


def summarise(data: dict) -> dict[str, dict[str, float]]:
    """Median of every timing over the runs after the first (run 1 is the cache warm-up)."""
    summary: dict[str, dict[str, float]] = {}
    for name, runs in data["results"].items():
        measured = runs[1:] or runs
        keys = {key for run in measured for key in run["steps"]}
        row = {"total": median(run["seconds"] for run in measured)}
        row["serialise"] = median(run["serialise_seconds"] for run in measured)
        for key in sorted(keys):
            row[key] = median(run["steps"].get(key, 0.0) for run in measured)
        summary[name] = row
    return summary


def print_summary(data: dict) -> None:
    """Print the medians of one result file."""
    for name, row in summarise(data).items():
        first = data["results"][name][0]
        print(f"\n{name}: routes={first['routes']}, subtrajectories={first['subtrajectories']}")
        for key, value in row.items():
            print(f"  {value:8.3f} s  {key}")


def compare(before_path: Path, after_path: Path) -> None:
    """Print medians side by side and whether the outputs are identical."""
    before = json.loads(before_path.read_text())
    after = json.loads(after_path.read_text())
    before_summary, after_summary = summarise(before), summarise(after)
    for name in before_summary.keys() & after_summary.keys():
        prints = {run["fingerprint"] for run in before["results"][name] + after["results"][name]}
        print(f"\n{name}: identical output={len(prints) == 1} ({', '.join(sorted(prints))})")
        for key in ("total", "serialise"):
            old, new = before_summary[name][key], after_summary[name][key]
            print(f"  {key:<62} {old:8.3f} -> {new:8.3f} s  ({old / max(new, 1e-9):5.1f}x)")
        keys = sorted((before_summary[name].keys() | after_summary[name].keys()) - {"total", "serialise"})
        for key in keys:
            old, new = before_summary[name].get(key, 0.0), after_summary[name].get(key, 0.0)
            print(f"  {key:<62} {old:8.3f} -> {new:8.3f} s")


def main() -> None:
    """Parse arguments and run, summarise or compare."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--src", type=Path, default=Path(__file__).resolve().parents[1] / "src")
    parser.add_argument("--cases", nargs="*", default=DEFAULT_CASES, choices=list(CASES))
    parser.add_argument("--large", action="store_true", help="run the large-area cases instead")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--compare", nargs=2, type=Path, metavar=("BEFORE", "AFTER"))
    args = parser.parse_args()

    if args.compare:
        compare(*args.compare)
        return
    data = run_benchmarks(args.src, LARGE_CASES if args.large else args.cases, args.runs)
    if args.out:
        args.out.write_text(json.dumps(data, indent=2))
    print_summary(data)


if __name__ == "__main__":
    main()
