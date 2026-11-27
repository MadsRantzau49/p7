"""Export real Porto A→B pieces once, or generate reproducible larger CSVs offline."""

import argparse
import os
from collections.abc import Iterator
from math import isqrt
from pathlib import Path
from random import Random

from benchmarks.datasets import (
    DATA,
    PORTO,
    XY,
    Row,
    find_fixture,
    fixture_origin,
    load_prefix,
    metric_frame,
    write_csv,
)

# The wide Porto query used in the application's previous end-to-end benchmarks.
BOX_A = (-8.658943176269533, 41.16185546825105, -8.561439514160158, 41.188472641161425)
BOX_B = (-8.652420043945314, 41.12048695593398, -8.561782836914064, 41.14246722711796)
PORTO_EXPORT = DATA / "bench_porto.csv"


def porto_rows(limit: int, seed: int, host: str, port: int) -> Iterator[Row]:
    """Reservoir-sample the ordered production extraction, then shuffle for unbiased nested prefixes."""
    import psycopg
    from database.repositories.trajectory_repository import TrajectoryRepository
    from dotenv import load_dotenv
    from models.bounding_box import BoundingBox
    from models.date_range import DateRange
    from services.subtrajectory_service import build_subtrajectory

    load_dotenv(Path(__file__).resolve().parents[3] / ".env")
    transformer = metric_frame(PORTO)
    rng = Random(seed)
    sample: list[Row] = []
    dates = DateRange(None, None)
    with psycopg.connect(
        host=host,
        port=port,
        dbname=os.environ["DATABASE_NAME"],
        user=os.environ["DATABASE_USER"],
        password=os.environ["DATABASE_PASSWORD"],
        connect_timeout=8,
        options="-c default_transaction_read_only=on -c statement_timeout=180000 -c TimeZone=UTC",
    ) as connection:
        with TrajectoryRepository(connection).stream_subtrajectories(
            BoundingBox(*BOX_A), BoundingBox(*BOX_B), None, None
        ) as rows:
            for i, row in enumerate(rows):
                slot = i if i < limit else rng.randrange(i + 1)
                if slot >= limit:
                    continue
                piece = build_subtrajectory(row, dates, i + 1)
                if piece is None:
                    raise ValueError("Unexpected date exclusion in the unbounded Porto query")
                xs, ys = transformer.transform(
                    [p.longitude for p in piece.points], [p.latitude for p in piece.points]
                )
                xy = [(round(x, 2), round(y, 2)) for x, y in zip(xs, ys, strict=True)]
                record = (i + 1, piece.trajectory_id, xy)
                if i < limit:
                    sample.append(record)
                else:
                    sample[slot] = record
    # Preserve shared trip identity and tie-break order without keeping DB IDs, dates or vehicle data.
    trip_ids = {trip: n for n, trip in enumerate(sorted({r[1] for r in sample}), start=1)}
    rng.shuffle(sample)
    for path_id, trip, xy in sample:
        yield path_id, trip_ids[trip], xy


def generated_rows(workload: str, count: int, seed: int, base: Path) -> Iterator[Row]:
    """Generate nested prefixes: changing count never changes any preceding row."""
    rng = Random(seed)
    templates: list[XY] = []
    if workload == "porto-jitter":
        paths, _ = load_prefix(base)
        templates = [[(p.x, p.y) for p in path.projected_points] for path in paths]
    if workload == "dense" and count > 2**27:
        raise ValueError("dense supports up to 2^27 distinct patterns")
    for i in range(count):
        xy: XY
        if workload == "porto-jitter":
            template = rng.choice(templates)
            dx, dy = rng.uniform(-12, 12), rng.uniform(-12, 12)
            xy = [
                (round(x + dx + rng.uniform(-3, 3), 2), round(y + dy + rng.uniform(-3, 3), 2))
                for x, y in template
            ]
        elif workload == "spread":
            # Fill successive square shells, rather than a line that would wrap around the earth.
            pair = i // 2
            side = isqrt(pair)
            offset = pair - side**2
            col, row = (offset, side) if offset <= side else (side, 2 * side - offset)
            x, y = 600 * col, 600 * row + round(rng.uniform(-5, 5), 2)
            xy = [(x, y), (x + 100, y + 20), (x + 200, y)]
        elif workload == "dense":
            # Common endpoints and bounds. A differing bit puts a vertex >100 m from the other curve.
            pattern = (i * 2654435761 + seed) % 2**27
            xy = [(0, 0), (500, 300)]
            xy.extend((500 * (bit + 2), 300 * ((pattern >> bit) & 1)) for bit in range(27))
            xy.append((14500, 0))
        else:
            raise ValueError(f"Unknown workload: {workload}")
        yield i + 1, i + 1, xy


def generate_csv(path: Path, workload: str, count: int, seed: int, base: Path) -> tuple[int, Path]:
    """Write builder-compatible GPS rows, keeping jittered templates in their original region."""
    if workload == "porto-jitter" and path.resolve() == base.resolve():
        raise ValueError("Output must differ from the template CSV")
    origin = fixture_origin(base) if workload == "porto-jitter" else PORTO
    return write_csv(path, generated_rows(workload, count, seed, base), origin=origin)


def positive(text: str) -> int:
    """Parse a positive count."""
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return value


def _fixture_path(text: str) -> Path:
    path = Path(text)
    return DATA / path if path.parent == Path(".") else path


def main() -> None:
    """Prepare a local CSV without running any benchmarks."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export-porto", help="read real A→B subpaths through an existing tunnel")
    export.add_argument("--host", default="127.0.0.1")
    export.add_argument("--port", type=int, default=15432)
    export.add_argument("--limit", type=positive, default=40000, help="maximum paths retained from query")
    export.add_argument("--seed", type=int, default=42)
    export.add_argument("--out", type=_fixture_path, default=PORTO_EXPORT)
    generate = commands.add_parser("generate", help="stream synthetic paths to a CSV, without a database")
    generate.add_argument("workload", choices=("porto-jitter", "spread", "dense"))
    generate.add_argument("--count", type=positive, required=True)
    generate.add_argument("--seed", type=int, default=42)
    generate.add_argument("--base", type=Path, default=DATA / "porto_sample.csv")
    generate.add_argument("--out", type=_fixture_path)
    args = parser.parse_args()
    if args.command == "export-porto":
        count, output = write_csv(args.out, porto_rows(args.limit, args.seed, args.host, args.port))
    else:
        output = args.out or DATA / f"bench_{args.workload}-{args.count}.csv"
        base = args.base
        if base.parent == Path("."):
            base = find_fixture(base.name) or DATA / base
        count, output = generate_csv(output, args.workload, args.count, args.seed, base)
    print(f"{count:,} subpaths written to {output} (seed={args.seed})")


if __name__ == "__main__":
    main()
