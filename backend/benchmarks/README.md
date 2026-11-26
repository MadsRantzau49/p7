# Find-routes benchmark

`find_routes_benchmark.py` runs the `/api/subtrajectories/get` handler in-process against a real
database. It records the step timings the services already log, the peak memory of the process,
and a fingerprint of the result (route counts, members and representative points), so two code
versions can be checked for identical output.

```bash
# Database through the SSH tunnel on localhost:15432 (password from ~/.pgpass)
python backend/benchmarks/find_routes_benchmark.py --runs 3 --out after.json
# The same searches with another checkout of the code
python backend/benchmarks/find_routes_benchmark.py --src /path/to/other/backend/src --out before.json
python backend/benchmarks/find_routes_benchmark.py --compare before.json after.json
# The large-area searches (minutes each)
python backend/benchmarks/find_routes_benchmark.py --large --runs 2 --out large.json
```

Run 1 of every search warms the database cache. The summaries are medians of the later runs.

## Results 2026-11-26: `performance` → `performance-optimisation`

Python ran on a laptop (WSL, 20 cores, 15 GB) and the database on the UCloud VM through the SSH
tunnel. Times in seconds, medians of the runs after the first (3 runs for the normal searches, 2
for the large ones). The clustering code is the same in both versions, so its differences
(up to about 20 %) show how noisy a single measurement is.

### Normal searches

All six returned identical output before and after.

| Search | Subtrajectories | Routes | Extraction | Clustering | Total | Speed-up |
|---|---:|---:|---:|---:|---:|---:|
| São Bento → Campanhã, July 2013 | 613 | 37 | 1.1 → 0.5 | 0.1 → 0.1 | 1.2 → 0.6 | 1.9x |
| São Bento → Campanhã, whole year | 7,126 | 314 | 9.6 → 2.8 | 2.7 → 2.9 | 12.4 → 5.8 | 2.1x |
| Same, epsilon 250 m | 7,126 | 168 | 8.7 → 3.0 | 4.2 → 4.4 | 12.9 → 7.4 | 1.7x |
| Centre (300 m apart), Oct 2013 | 431 | 26 | 1.4 → 0.7 | 0.0 → 0.0 | 1.5 → 0.7 | 2.0x |
| Campanhã → São João, whole year | 107 | 35 | 3.1 → 0.9 | 0.0 → 0.0 | 3.1 → 1.0 | 3.3x |
| Beijing Railway Station → Beijing West, all | 1,489 | 1,372 | 6.9 → 4.4 | 0.7 → 0.8 | 7.7 → 5.3 | 1.4x |

Two users searching the whole year São Bento → Campanhã at the same time: 13.2 s and 13.7 s
before, 7.8 s and 8.3 s after.

### Large areas, the whole Porto year

Downtown (around São Bento and Aliados) to Boavista, the two busiest areas, with growing boxes,
and a near worst case of about 3 × 2.4 km downtown to 3.7 × 3.3 km of the west, 330 m apart.

| Search | Subtrajectories | Routes | Extraction | Clustering | Total | Speed-up | Peak memory (MB) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Boxes 500 × 500 m | 2,263 | 509 → 509 | 11.4 → 3.9 | 1.4 → 1.1 | 12.9 → 5.1 | 2.5x | 148 → 151 |
| Boxes 1 × 1 km | 16,302 | 1,653 → 1,652 | 16.6 → 9.2 | 8.4 → 6.6 | 25.3 → 16.0 | 1.6x | 455 → 463 |
| Boxes 2 × 2 km | 126,058 | 2,570 → 2,568 | 65.8 → 42.4 | 32.7 → 26.3 | 99.5 → 69.4 | 1.4x | 1,475 → 1,488 |
| Near worst case | 203,967 | 2,763 → 2,762 | 62.0 → 49.0 | 32.8 → 27.6 | 96.0 → 77.6 | 1.2x | 1,618 → 1,633 |

The route counts of the three larger searches differ because of a bug in the old code, see
change 3. All the differing subtrajectories (1, 4 and 2) cross the hour when summer time ends,
and clustering gives identical results when both versions get the same subtrajectories.

Raw results are in `results/`.

## What changed

1. **Parallel date chunks** (`SubtrajectoryService`, `split_dates`). The database spent most of
   the search checking candidate trips one by one on a single CPU core. A bounded date range is
   now split into `SUBTRAJECTORY_QUERY_CHUNKS` (default 4) ranges of whole days, queried at the
   same time on separate pooled connections. Each chunk keeps only pieces that leave A on its own
   local dates, so nothing is counted twice. The pieces are sorted by trajectory and exit
   instant and numbered as before. The pool now holds up to `DATABASE_POOL_MAX_SIZE` (default 10)
   connections. 8 chunks were no faster than 4 on the VM.
2. **Interior points cut in SQL** (`TrajectoryRepository`). The query used to send every point of
   the whole trajectory as JSON, and Python parsed every timestamp to keep the ones between leaving
   A and entering B. The query now returns only those points, as three arrays. The points are
   still taken from the stored JSON, not from the MobilityDB piece: MobilityDB drops collinear
   and repeated points, which changed 420 of 7,126 pieces in the whole-year search.
3. **Summer-time bug fixed as a side effect.** The old Python filter compared local times that
   share a `tzinfo`, and Python compares those by wall-clock time. In the hour after summer time
   ends (27 October 2013, 01:00 UTC in Lisbon), a trip can leave A at 01:56 summer time and enter
   B at 01:02 winter time. No point is then "after 01:56 and before 01:02", so the old code
   dropped every point in between and the route became a straight line from A to B. The SQL
   compares instants. The merge sort of the chunks also sorts by instant.

Tried and not kept: an exact "footprint" filter in clustering (every vertex of a route must lie
in the grid cells around the other route). It cut the Fréchet evaluations on the whole-year
search from 25,172 to 8,227, but on the same inputs the clustering time stayed within about 10 %
of the old code, slower on the large searches. Most of the work is the Fréchet checks that
succeed (201,205 of them in the near worst case), and no exact filter can skip those.

## Where the time goes now

- **Database.** In the whole-year São Bento → Campanhã search, the trip index returns 89,042
  candidate trips and the exact check (`eIntersects`) drops 79,310 of them. A trip's bounding box
  covers its whole route, so trips that pass near both boxes at different times or places are
  candidates too. Fewer candidates need smaller boxes per trip (for example a table of
  `splitNStboxes` boxes per trip, or the multi-entry indexes of Schoemans et al. 2024). That is a
  schema change and was not tried.
- **Clustering, from 100,000 subtrajectories up about 25–35 s.** The number of routes levels off
  (about 2,700 routes for 126,000 and 204,000 subtrajectories), so clustering grows roughly in
  proportion to the number of subtrajectories, but every one of them needs at least one Fréchet
  check in pure Python. Compiled code (Numba, Cython or Rust) would be the next step, but it is a
  new dependency.
- **Building the subtrajectories in Python** for the large searches. The 4 chunks run in threads,
  and the Python part of each chunk shares one core. The split between database time and Python
  time in the large searches was not measured.
- **Memory.** The near worst case peaks at about 1.6 GB in both versions, almost all of it the
  204,000 subtrajectories as Python objects.

Known limitation of the tests: the MobilityDB 1.3 Docker image did not start locally, and the
integration test with unbounded dates fails on MobilityDB 1.4 ("The timestamp must be finite")
both before and after this change. The VM runs MobilityDB 1.3.
