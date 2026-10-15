import { useMemo } from "react";
import type { PathletClusteringResult } from "../models/pathlet";

interface PathletTimingsProps {
  runs: PathletClusteringResult[];
  useSpatialIndex: boolean;
  useBoundingBoxFilter: boolean;
}

function delta(value: number): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(3)} ms`;
}

export default function PathletTimings({ runs, useSpatialIndex, useBoundingBoxFilter }: PathletTimingsProps) {
  const samePathlets = useMemo(() => runs.length >= 2
    ? runs.every((run) => JSON.stringify(run.pathlets) === JSON.stringify(runs[0].pathlets)) : null, [runs]);
  if (runs.length === 0) return null;

  const findRun = (indexed: boolean, filtered: boolean) => runs.find((run) =>
    run.metrics.use_spatial_index === indexed && run.metrics.use_bounding_box_filter === filtered);
  const rows = [
    { indexed: true, filtered: true }, { indexed: false, filtered: true },
    { indexed: true, filtered: false }, { indexed: false, filtered: false },
  ];
  const withIndex = findRun(true, useBoundingBoxFilter);
  const withoutIndex = findRun(false, useBoundingBoxFilter);
  const withFilter = findRun(useSpatialIndex, true);
  const withoutFilter = findRun(useSpatialIndex, false);

  return <section className="pathlet-timings" aria-label="Performance comparison">
    <h3>Candidate search comparison</h3>
    <div className="pathlet-timing-scroll">
      <table aria-label="Spatial index timing comparison">
        <caption>Latest backend timings (ms)</caption>
        <thead><tr><th scope="col">Mode</th><th scope="col">Build</th>
          <th scope="col">Search</th><th scope="col">Total</th></tr></thead>
        <tbody>{rows.map(({ indexed, filtered }) => {
          const result = findRun(indexed, filtered);
          return <tr key={`${indexed}-${filtered}`}>
            <th scope="row">{indexed ? "With index" : "Without index"}
              <small>Filter {filtered ? "on" : "off"}</small>
              {result && <small>{result.metrics.sspd_comparison_count.toLocaleString()} pairs<br />
                SSPD: {result.metrics.step_runtime_ms["05_sspd"].toFixed(3)} ms</small>}
            </th>
            {result ? <>
              <td>{result.metrics.step_runtime_ms["03_spatial_index"].toFixed(3)}</td>
              <td>{result.metrics.step_runtime_ms["04_nearby_pairs"].toFixed(3)}</td>
              <td>{result.metrics.total_runtime_ms.toFixed(3)}</td>
            </> : <td colSpan={3}>Not run</td>}
          </tr>;
        })}</tbody>
      </table>
    </div>
    {withIndex && withoutIndex && <p className="pathlet-help">
      Index difference (without − with, filter {useBoundingBoxFilter ? "on" : "off"}):<br />
      Total: {delta(withoutIndex.metrics.total_runtime_ms - withIndex.metrics.total_runtime_ms)}<br />
      Build + search: {delta(withoutIndex.metrics.candidate_discovery_runtime_ms
        - withIndex.metrics.candidate_discovery_runtime_ms)}
    </p>}
    {withFilter && withoutFilter && <p className="pathlet-help">
      Filter difference (off − on, {useSpatialIndex ? "with" : "without"} index):<br />
      Total: {delta(withoutFilter.metrics.total_runtime_ms - withFilter.metrics.total_runtime_ms)}<br />
      SSPD: {delta(withoutFilter.metrics.step_runtime_ms["05_sspd"] - withFilter.metrics.step_runtime_ms["05_sspd"])}
    </p>}
    {samePathlets !== null && <p className={samePathlets ? "pathlet-help" : "trajectory-error"}
      role={samePathlets ? "status" : "alert"}>
      {samePathlets ? (runs.length === 2 ? "Same pathlets and assignments in both modes."
        : "Same pathlets and assignments in all completed runs.") : "The settings returned different pathlets."}
    </p>}
    <p className="pathlet-help">
      {runs[0].metrics.possible_cross_trajectory_pair_count.toLocaleString()} possible cross-trajectory pairs.
      {" "}Filter-on rows reject distant pairs. Filter-off rows send every pair to SSPD;
      indexed queries cover the full extent and do not prune pairs.
    </p>
    <p className="pathlet-help">
      Total includes index construction and all algorithm stages; network and rendering are excluded.
      {" "}Single-run measurements vary; repeat the comparison to check warm-up and timing noise.
    </p>
  </section>;
}
