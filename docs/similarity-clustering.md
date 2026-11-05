# Continuous pathlet clustering

With the virtual environment active, run from the repository root:

```sh
PYTHONPATH=backend/src python -m services.similarity_service
```

The example currently selects the 10,000-point Aarhus city fixture at epsilon
300 metres and writes `backend/tests/data/pathlets.json`. It logs projection,
continuous extension, inverse projection and the total pipeline time. CSV loading
and JSON output are outside the logged pipeline total.

## Long representatives and partial support

Pathlets grow along original trajectory geometry. Supporting trajectories can
join, leave, or travel in the opposite direction without splitting that geometry.
Differently sampled trajectories can match: several short segments may follow
one longer segment, and the two matching cursors can move at different rates.

The output includes:

```json
{
  "points": ["original representative GPS coordinates"],
  "count": 3,
  "support": [
    {"start_m": 0.0, "end_m": 200.0, "count": 2},
    {"start_m": 200.0, "end_m": 400.0, "count": 3},
    {"start_m": 400.0, "end_m": 600.0, "count": 2}
  ]
}
```

The top-level `count` is distinct original trajectory IDs contributing anywhere
along this pathlet, including its representative. `support` gives the local
count over each interval's interior. Distances are arc lengths from the first
representative point, measured in the common projected coordinate system.
Repeated or overlapping sections from the same original trajectory count once.
Stationary matches may contribute at a single position rather than over a
positive-length interval.

Internally, each assigned `TrajectorySection` retains its original section ID,
original vertex range, matched representative start/end distances, and travel
orientation. This allows a partial supporter to be checked against its actual
matched interval, rather than against the entire longer representative.

## Epsilon

Epsilon is an inclusive maximum matching distance in projected metres, rather
than an average SSPD distance. A monotone cursor follows each path. The distance
is checked at source vertices and at every representative corner crossed inside
a source segment. Between those breakpoints both interpolated paths are straight,
so the endpoint checks bound the whole continuous matching.

The representative cursor can pause at an endpoint if the supporting geometry
remains within epsilon. Every assignment is checked directly against its own
representative interval; transitive chains do not relax the tolerance. The
matcher is greedy and conservative, so it can split a geometrically plausible
match when its local continuation fails.

## Algorithm and coverage

1. Project each input section with one native PROJ call and prepare compact
   arc-length arrays.
2. Process longer sections first. Locate starting matches in an incremental grid
   containing only representative edges. Cached edge geometry and expanded
   boxes cheaply filter candidates; exceptionally long edges have a sparse
   fallback instead of allocating huge grid rectangles.
3. Prefer continuing, extended corridors over crossings and short dead ends.
   Advance the first valid matching cursors incrementally through a continuous
   source section. Only complete source segments are committed.
4. Grow unmatched original geometry into a new representative until an existing
   continuous match begins. Supporter changes do not end a representative.
5. Merge support intervals per original trajectory ID and compute local counts
   using an event sweep, then inverse-project the representatives.

Every original segment is assigned exactly once, including zero-length segments.
Single-point sections are also preserved. Geometry and original vertex order
are retained; coverage is tracked separately for different input sections even
when they share a source trajectory ID. The algorithm stores chosen intervals
rather than all matching pairs or every extended candidate prefix.

`r_tree_max_entries` remains accepted by the service for compatibility. The new
engine uses the incremental representative grid instead of building an R-tree
over every original segment.

## Reproducible benchmarks

```sh
PYTHONPATH=backend/src python backend/tests/benchmark_similarity.py \
  backend/tests/data/trajectories/aarhus_city_10000_points.csv \
  backend/tests/data/trajectories/aarhus_city_100000_points.csv \
  --epsilon 100 --verify
```

The same command accepts fixtures from `backend/tests/data/large_trajectories/`.
It reports CSV loading separately from the pipeline, pathlet lengths, residual
single-segment pathlets, and the fraction of original distance represented by
multi-segment pathlets. `--verify` additionally checks exact segment coverage and
symmetric distances to the matched intervals using GEOS/Shapely. Verification
and statistics are excluded from the pipeline timer.

Some short pathlets remain for uncovered original geometry; minimum output
length is not enforced by dropping those segments. Evaluate the distance covered
by extended pathlets alongside the unweighted pathlet count.

Example local measurements at epsilon 100 metres:

| Fixture | Pipeline | Pathlets | Longest representative | Input distance on extended pathlets |
| --- | ---: | ---: | ---: | ---: |
| City, 10,000 points | 0.10 s | 375 | 6.94 km | 92.9% |
| City, 100,000 points | 1.10 s | 518 | 8.46 km | 90.2% |
| City, 1,000,000 points | 9.35 s | 518 | 9.88 km | 89.9% |
| Aarhus–Randers, 100,000 points | 0.70 s | 44 | 43.77 km | 97.8% |
| Aarhus–Randers, 1,000,000 points | 7.18 s | 47 | 43.77 km | 96.8% |

These are observed timings, not hard runtime limits. The complete
million-point example command took 26.12 seconds including CSV parsing, startup,
support metadata serialization and JSON writing; its logged clustering pipeline
took 9.35 seconds. CSV loading alone takes approximately 11 seconds on these
million-point fixtures. Both million-point fixtures passed exact segment coverage
and independent matched-interval distance verification.

## Correctness tests

```sh
python -m pytest backend/tests/unit/test_similarity_service.py
```

Tests cover partial support and handoffs, reverse travel, unequal sampling,
reference bends inside long source segments, tolerance boundaries, loops,
repeated source IDs, zero-length observations, projection roundtrips and exact
coverage. Spatial filtering is checked against exhaustive seed enumeration.
