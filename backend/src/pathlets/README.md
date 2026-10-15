# SSPD pathlets

Deterministic, independent geometric clustering. `main.run_pipeline` calls every
stage explicitly; there are no database, API, training, or plotting dependencies
in the geometric steps. Python syntax follows the repository's 3.10 target;
the repository CI runs Python 3.12.

## Run

From the repository root, using its virtual environment:

```bash
venv/bin/python -m pip install -r requirements.txt
PYTHONPATH=backend/src venv/bin/python -m pathlets.main \
  --input backend/tests/data/trajectories/aalborg_germany.csv \
  --epsilon 100 --debug
```

The fixture has **8 trajectories, 198 points, 190 original segments**, including
one stationary segment. Its actual header is:

```text
trajectory_id,vehicle_id,vehicle_type,timestamp,longitude,latitude,city,source_id,database_trajectory_id
```

The loader reuses `helpers.upload_parser.parse_upload` and the existing
`UniformedTrajectoryPoint` model. It preserves string CSV trajectory IDs,
optional metadata, source row numbers, point order, and timestamps. IDs are not
replaced by `database_trajectory_id`. Rows within each trajectory must already
have increasing timestamps; recordings from different cars need not overlap in
time. Malformed files produce a nonzero CLI exit with line-level errors.

This hand-drawn fixture has kilometer-scale offsets and sparse samples. A
100 m threshold finds only small shared portions; to inspect broader corridors:

```bash
PYTHONPATH=backend/src venv/bin/python -m pathlets.main \
  --input backend/tests/data/trajectories/aalborg_germany.csv \
  --epsilon 2000 --debug \
  --output-dir outputs/pathlets/corridors \
  --debug-output-dir debug/pathlets/corridors
```

`epsilon_m` is an inclusive **projected distance in meters**. A user-facing
similarity percentage is a separate interface concern: no percentage-to-distance
mapping is assumed or implemented. A future mapping must be an explicitly
configured, experimentally justified strategy outside the geometry pipeline.

## Outputs and diagnostics

Every CLI run writes `pathlets.json` and `metrics.json` to `--output-dir` (default
`outputs/pathlets`). The JSON contains configuration, projection WKT, original
GPS trajectories/metadata, and final pathlets. Each pathlet includes:

- A stable ID, ordered **`[latitude, longitude]`** coordinates for Leaflet,
  distinct source IDs, and `count` (not matching-segment count).
- Its representative source interval and each contributor's assignment interval,
  interpolated endpoint timestamps, source CSV rows, and maximum assignment SSPD.

Assignments represent **only the specified portion** of each source trajectory.
Positions are fractional original point indices: `[1.25, 4]` starts one quarter
of the way from source point 1 to point 2 and ends at point 4. Geometry between
those endpoints includes **all original interior vertices**. Timestamps are
interpolated by segment fraction, independently per car. Adjacent assignments
share a boundary point but never duplicate a positive source interval.

With `--debug`, all nine complete numerical snapshots are saved, along with:

```text
01_metric_trajectories.png    02_segments.png
03_bounding_boxes.png         04_nearby_pairs.png
05_sspd_matches.png           06_candidate_clusters.png
07_extended_pathlets.png      08_selected_pathlets.png
09_final_gps_pathlets.html    metrics.json
```

`--debug-steps 3,5,8,9` selects plots; snapshots still retain every intermediate
result. Static plots sample large stages; HTML includes **every** final pathlet
and its assignments. The HTML needs internet access for Leaflet and map tiles.
Re-render a stage independently, without rerunning clustering:

```bash
PYTHONPATH=backend/src venv/bin/python -m pathlets.visualization \
  --snapshot debug/pathlets/05_sspd_matches.json --sample-size 30
```

Visualization is an optional observer and cannot change selection. Headless
runs do not import Matplotlib or the visualization module.

## Stage contracts and replacement

`models.py` contains frozen dataclasses for intermediate geometry and provenance,
plus `ClusteringConfig` and typed metrics. Replace a function at its explicit call
in `main.py`, retaining its input/output contracts:

| Stage | Function/module | Policy |
| --- | --- | --- |
| Load | `loading.load_trajectories` | Validated CSV; `from_uniformed(id, model)` adapts existing backend data. |
| 1 | `geometry.convert_to_meters` | Ellipsoidal local azimuthal equidistant projection; inverse WKT retained. |
| 2 | `geometry.generate_segments` | All consecutive original edges, including zero-length edges. |
| 3 | `spatial.build_spatial_index` | Optional Shapely 2 `STRtree`; tree positions mapped explicitly to segment IDs. |
| 4 | `spatial.find_nearby_pairs` / `find_nearby_pairs_brute_force` | Optional expanded-box filtering, or every cross-source pair; unique unordered pairs. |
| 5 | `spatial.compare_sspd` | Reusable `geometry.sspd`, inclusive `distance <= epsilon`. |
| 6 | `spatial.construct_candidate_clusters` | Representative stars, never transitive connected components. |
| 7 | `extension.extend_clusters` | Directed clipped-overlap atoms, bounded prefix extension and full SSPD rechecks. |
| 8 | `selection.select_final_pathlets` | Deterministic disjoint greedy coverage, then singleton complements. |
| 9 | `selection.convert_to_gps` | Inverse projection, contributor count, interval/timestamp provenance. |

For in-memory integration, call `run_pipeline(config, trajectories=gps_models)`
with `ClusteringConfig(epsilon_m=..., output_dir=None)`: file loading and artifact
writes are bypassed. The frontend API uses this mode and returns pathlets and
metrics directly to the existing Leaflet map; see the
[frontend guide](../../../frontend/README.md). Individual metric stages also accept timestamp-free
`MetricTrajectory` objects (`None` timestamps).

### Geometry and search guarantees

Projection uses circular longitude averaging, including local dateline crossings.
The extent is measured geodesically before projection. Inputs beyond the
configured radius (at most 1000 km) are rejected with a partitioning instruction.
At 1000 km, a spherical AEQD estimate of worst transverse scale error is about
0.42%; this is not Web Mercator or unrestricted single-zone UTM. The supplied
fixture's radius is about 137.4 km, giving approximately 0.008% scale error.

SSPD is exactly the average of the two directed mean vertex-to-polyline
distances. Original sampling weights and duplicate vertices are retained; it is
not Hausdorff distance and does not bound every individual point's deviation.
Hot loops use scalar Euclidean geometry, not newly allocated Shapely objects.
Floating-point roundoff still applies; use a small positive epsilon rather than
expecting exact zero after fractional interpolation or projection.

The default search radius is `4 * epsilon`: for two-endpoint SSPD each of the
four endpoint distances is at most `4 * epsilon`, so this bounding-box search is
conservative. Smaller radii require `approximate_search=True` /
`--approximate-search`, which can miss valid matches. Spatial proximity alone
never proves a match.

### Optional spatial index and timing comparisons

`ClusteringConfig(use_spatial_index=True, use_bounding_box_filter=True)` is the
default. The flags are independent:

| Index | Bounding-box filter | Candidate discovery |
| --- | --- | --- |
| On | On | STRtree queries within expanded segment boxes. |
| Off | On | Scan cross-source pairs using cached bounds and the same inclusive expanded-box predicate. |
| On | Off | Build STRtree, query the complete dataset extent once, then enumerate all cross-source pairs from the returned entries. |
| Off | Off | Enumerate all cross-source pairs without reading segment bounds or the search radius. |

Disabling the index skips stage 3 entirely. Disabling the filter sends every
cross-source pair to `compare_sspd` and the overlap-seeding stage; no distance
rejection occurs during discovery. Index-on/filter-off retains tree construction
and its full-extent query for overhead comparison but cannot accelerate pruning.
All emitted pairs remain unique and sorted identically. The conservative default
radius preserves SSPD matches and final assignments across these settings in
the tested cases. Explicit approximate filtered searches can miss matches;
disabling the filter also disables that radius restriction.

Unfiltered discovery stores O(n²) candidate references and performs O(n²) SSPD
comparisons; unlike the filtered scan, it must retain the complete pair list.
The similarity threshold and all later geometric checks remain active.

CLI example:

```bash
PYTHONPATH=backend/src venv/bin/python -m pathlets.main \
  --input backend/tests/data/trajectories/aalborg_germany.csv \
  --epsilon 2000 --no-spatial-index --output-dir outputs/pathlets/no-index
```

Use `--spatial-index` (or omit either flag) for indexed discovery. The frontend
API accepts both flags. To disable every broad-phase filter, add
`--no-spatial-index --no-bounding-box-filter`; `--bounding-box-filter` restores
the default distance filter. Its search radius is unused when filtering is off.
The frontend's **Compare both modes** uses the current filter setting; toggle
the filter and compare again to populate all four timing rows. Metrics record
both flags, `sspd_comparison_count`, the selected search method,
`possible_cross_trajectory_pair_count`, and `candidate_discovery_runtime_ms`.
The latter sums `03_spatial_index` and `04_nearby_pairs`; the skipped stage is
exactly zero in the baseline. `spatial_candidate_pair_count` retains its original
field name but counts emitted candidates in every setting (all possible pairs
when filtering is off). Each row also shows stage `05_sspd` runtime. Total runtime
includes tree construction. Small inputs can be faster without indexing because
of index overhead; single-run timings vary with warm-up and system load.

### Extension and selection trade-offs

1. Whole-segment match stars supply initial seed pairs. **Supplemental clipped
   seeds** from the same nearby candidates handle unequal sampling: whole-edge
   SSPD can fail even for two overlapping pieces of the same straight road.
2. For each directed pair, project endpoints onto the representative, clip the
   longitudinal overlap, project its endpoints back onto the other edge, and
   check clipped SSPD. Default direction cosine is at least `0.5` (60 degrees),
   with strictly positive progression. Opposite-direction travel is separate.
3. Sweep overlap endpoints to build atoms of constant contributor membership.
   Recheck every atom. Multiple source segments from one car compete by distance
   and interval order; only one assignment per car is retained. This can choose
   a locally nearest visit over a globally more extensible visit.
4. Try at most `max_extension_steps` atoms from each start (default 100). Support
   changes stop extension. Same-support seeds can overlap or bridge a source
   arc-length gap up to `extension_gap_m` (default `2 * epsilon`, configurable via
   `--extension-gap`). Every source interval progresses forward. Gaps are filled
   with original route geometry, not straight-line shortcuts.
5. Evaluate **every** whole-prefix SSPD, continuing after failed prefixes because
   SSPD is not monotonic. Save each atom and the longest passing prefix per start.
   Bounded windows, clipping, direction filtering, and omitted intermediate
   prefixes mean this search is **heuristic, neither complete nor optimal**.
6. Rank candidates by summed assigned source meters, then distinct support and
   stable source/interval ordering. Accept a candidate only if every assignment
   is wholly uncovered. This suppresses reciprocal/near-duplicate candidates
   consuming the same sources without collapsing distinct repeated visits.
   Partial overlaps are rejected rather than inventing new assignment boundaries;
   their leftovers may therefore be fragmented or singleton instead of shared.
7. Fill the exact interval-union complement with singleton paths. The minimum
   pathlet length only filters shared proposals, never singleton coverage. A
   runtime validator checks complete, non-overlapping coverage in original
   point-index space, so stationary intervals cannot disappear.

Support changes create split/rejoin boundaries. Sampling offsets can leave small
singleton gaps, and SSPD's mean-distance definition can admit modest deviations
within a shared path. Counts describe selected assignments, not a claim that all
other nearby trajectories must also belong to that representative.

## Verification and observed performance

```bash
venv/bin/pytest backend/tests/unit/test_pathlets.py backend/tests/integration/test_pathlets_pipeline.py
venv/bin/ruff check backend/src/pathlets backend/tests/unit/test_pathlets.py backend/tests/integration/test_pathlets_pipeline.py
venv/bin/ruff format --check backend/src/pathlets backend/tests/unit/test_pathlets.py backend/tests/integration/test_pathlets_pipeline.py
venv/bin/pyright backend/src/pathlets backend/tests/unit/test_pathlets.py backend/tests/integration/test_pathlets_pipeline.py
```

The tests cover every stage, exact SSPD and threshold equality, R-tree discovery
against a brute-force *test oracle*, nontransitive stars, unequal sampling,
direction/repeated visits, gap rechecks, nonmonotonic extension, split/rejoin
counts, stationary/singleton coverage, independent timestamps, deterministic
results, headless/CLI execution, and every debug artifact on the real fixture.

An observed 2 km fixture run produced 1,139 spatial pairs, 56 whole-segment
matches, 943 extended candidates, and 154 final pathlets (56 shared, support
2–7; 98 singleton). All 190 original intervals were covered. These are measured
outputs, not hardcoded cluster expectations. The static result shows the main
eastern corridor, central branch, and southern rejoin; singleton western/eastern
detours remain visible. At 100 m, only seven short shared portions are found.

On this environment the 2 km algorithm took about 150 ms, with extension around
95 ms; debug serialization and eight PNGs plus HTML took about 3.5 seconds.
`total_runtime_ms` measures the algorithm including loading and coverage checks;
`artifact_runtime_ms` measures output/debug work separately. Timings vary by run.

Extension is the observed computational bottleneck: full polyline SSPD is
quadratic in the two vertex counts. Its search window, 65,536-entry geometry /
distance caches, and at-most-two stored candidates per atom bound repeated work.
R-tree discovery is output-sensitive; very dense overlapping corridors can
still produce quadratically many valid nearby pairs and large local memberships.
No arbitrary pair cap silently discards these. Selection uses sorted interval
lists and binary-search overlap checks; list insertion can become costly on very
fragmented large inputs. Debug snapshots deliberately keep complete data and can
be large. Larger-scale optimization should target these measured stages through
their independent contracts.

Ruff and Pyright pass repository-wide. Vulture's default 60%-confidence scan
reports serialized projection / TypedDict schema members as unused attributes;
they are required JSON fields, not dead code. Its 100%-confidence scan is clean.
