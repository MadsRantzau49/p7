# Clustering fixtures

- **`trajectories/`** holds versioned trajectory-builder CSVs (one row per GPS point). Commit fixtures **under 100 MiB** here. The regular CI suite uses this folder, including small prefixes of the real Porto, jitter, spread and dense workloads. A clean checkout needs no SSH tunnel to test clustering.
- **`large_trajectories/`** holds local-only CSVs. Only `.gitkeep` is tracked. The benchmark generator automatically places outputs of **100 MiB or more** here; you can also move large hand-made CSVs here yourself. Local lookup checks `trajectories/` first, then this folder. When `CI=true` the second folder is excluded from collection, lookup, loading and generation.

```sh
pytest backend/tests/benchmarks                      # Fast correctness tests; runs in CI
pytest -m slow backend/tests/benchmarks               # Standard sizes and epsilon sweep
pytest -m extra_test -k porto-1M backend/tests/benchmarks   # Large local benchmark
```

Named builder CSVs in `trajectories/` use `slow`; named builder CSVs in `large_trajectories/` use `extra_test`.
`bench_*` is reserved for parameterized benchmark workloads, which look up their CSV by filename in both locations locally.
For a custom local `my_routes.csv`, run:

```sh
pytest -m extra_test 'backend/tests/benchmarks/test_scale.py::test_builder_fixture[my_routes]'
```

Generate a missing local synthetic workload on demand by selecting its benchmark, or explicitly:

```sh
PYTHONPATH=backend/src:backend/tests python -m benchmarks.prepare generate porto-jitter --count 100000
```
