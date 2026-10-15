import { useEffect, useRef, useState } from "react";
import type { SubmitEvent } from "react";
import { clusterTrajectories, getPathletError, previewTrajectoryCsv } from "../api/pathletAPI";
import type { PathletClusteringResult } from "../models/pathlet";
import type { uniformedTrajectoryResponse } from "../models/uniformedTrajectoryResponse";
import PathletTimings from "./pathletTimings";

interface ComparedRuns {
  trajectories: uniformedTrajectoryResponse[];
  epsilonM: number;
  runs: PathletClusteringResult[];
}

interface PathletPanelProps {
  trajectories: uniformedTrajectoryResponse[];
  result: PathletClusteringResult | null;
  disabled: boolean;
  showPathlets: boolean;
  showOriginals: boolean;
  onPreviewLoaded: (trajectories: uniformedTrajectoryResponse[], name: string) => void;
  onResultChange: (result: PathletClusteringResult | null) => void;
  onBusyChange: (busy: boolean) => void;
  onShowPathletsChange: (show: boolean) => void;
  onShowOriginalsChange: (show: boolean) => void;
}

export default function PathletPanel({
  trajectories, result, disabled, showPathlets, showOriginals,
  onPreviewLoaded, onResultChange, onBusyChange, onShowPathletsChange, onShowOriginalsChange,
}: PathletPanelProps) {
  const [epsilon, setEpsilon] = useState("100");
  const [useSpatialIndex, setUseSpatialIndex] = useState(true);
  const [useBoundingBoxFilter, setUseBoundingBoxFilter] = useState(true);
  const [comparedRuns, setComparedRuns] = useState<ComparedRuns | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [operation, setOperation] = useState<"preview" | "cluster" | "compare" | null>(null);
  const [error, setError] = useState("");
  const request = useRef<AbortController | null>(null);

  useEffect(() => () => request.current?.abort(), []);

  async function handlePreview(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file || disabled || operation) return;
    const controller = new AbortController();
    request.current = controller;
    setError("");
    setOperation("preview");
    onBusyChange(true);
    try {
      const data = await previewTrajectoryCsv(file, controller.signal);
      if (!controller.signal.aborted) onPreviewLoaded(data, file.name);
    } catch (failure) {
      if (!controller.signal.aborted) setError(getPathletError(failure));
    } finally {
      if (!controller.signal.aborted) {
        setOperation(null);
        onBusyChange(false);
      }
    }
  }

  async function handleCluster(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    await runClustering(false);
  }

  async function runClustering(compare: boolean) {
    if (disabled || operation || trajectories.length === 0) return;
    const epsilonM = Number(epsilon);
    if (!epsilon.trim() || !Number.isFinite(epsilonM) || epsilonM < 0) {
      setError("Enter a nonnegative SSPD distance in meters.");
      return;
    }
    const controller = new AbortController();
    request.current = controller;
    setError("");
    setOperation(compare ? "compare" : "cluster");
    onBusyChange(true);
    onResultChange(null);
    try {
      const modes = compare ? [useSpatialIndex, !useSpatialIndex] : [useSpatialIndex];
      for (const mode of modes) {
        const data = await clusterTrajectories(trajectories, epsilonM, mode, useBoundingBoxFilter, controller.signal);
        if (controller.signal.aborted) return;
        setComparedRuns((previous) => {
          const history = previous?.trajectories === trajectories && previous.epsilonM === epsilonM
            ? previous.runs : [];
          return { trajectories, epsilonM, runs: [
            ...history.filter((run) => run.metrics.use_spatial_index !== mode
              || run.metrics.use_bounding_box_filter !== useBoundingBoxFilter), data,
          ] };
        });
        if (mode === useSpatialIndex) onResultChange(data);
      }
    } catch (failure) {
      if (!controller.signal.aborted) setError(getPathletError(failure));
    } finally {
      if (!controller.signal.aborted) {
        setOperation(null);
        onBusyChange(false);
      }
    }
  }

  const busy = disabled || operation !== null;
  const currentRuns = comparedRuns?.trajectories === trajectories && comparedRuns.epsilonM === Number(epsilon)
    ? comparedRuns : null;

  return (
    <section className="pathlet-panel" aria-labelledby="pathlet-heading" aria-busy={operation !== null}>
      <h2 id="pathlet-heading">Shared paths</h2>
      <p className="pathlet-help">
        Combine common corridors into pathlets. Line width shows how many distinct trajectories follow each portion.
      </p>

      <form onSubmit={handlePreview}>
        <fieldset disabled={busy}>
          <div className="trajectory-field">
            <label htmlFor="pathlet-csv">Open a trajectory CSV</label>
            <input id="pathlet-csv" type="file" accept=".csv,text/csv"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
            <small>Preview a CSV on this map, or use trajectories loaded above.</small>
          </div>
          <button type="submit" className="trajectory-list-toggle" disabled={busy || !file}>
            {operation === "preview" ? "Opening CSV…" : "Open CSV on map"}
          </button>
        </fieldset>
      </form>

      <form onSubmit={handleCluster} className="pathlet-cluster-form">
        <fieldset disabled={busy}>
          <div className="trajectory-field">
            <label htmlFor="pathlet-epsilon">SSPD threshold (meters)</label>
            <input id="pathlet-epsilon" type="number" min="0" step="any" required value={epsilon}
              onChange={(event) => {
                setEpsilon(event.target.value);
                setComparedRuns(null);
                setError("");
                onResultChange(null);
              }} />
            <small>Lower values require closer routes. This is a distance, not a similarity percentage.</small>
          </div>
          <label className="pathlet-checkbox">
            <input type="checkbox" checked={useSpatialIndex}
              onChange={(event) => {
                setUseSpatialIndex(event.target.checked);
                setError("");
                onResultChange(null);
              }} />
            Use spatial index (STRtree)
          </label>
          <p className="pathlet-help">Uncheck to scan pairs without building an index.</p>
          <label className="pathlet-checkbox">
            <input type="checkbox" checked={useBoundingBoxFilter}
              onChange={(event) => {
                setUseBoundingBoxFilter(event.target.checked);
                setError("");
                onResultChange(null);
              }} />
            Use bounding-box distance filter
          </label>
          <p className="pathlet-help">
            {useBoundingBoxFilter ? "Filter out distant segment pairs before SSPD."
              : "Every cross-trajectory segment pair reaches SSPD. Indexed queries cover the full dataset."}
            {" "}Compare both modes uses this filter setting; previous settings stay in the timing table.
          </p>
          <button type="submit" className="trajectory-submit" disabled={busy || trajectories.length === 0}>
            {operation === "cluster" ? "Clustering…" : "Cluster loaded trajectories"}
          </button>
          <button type="button" className="trajectory-list-toggle pathlet-compare-button"
            disabled={busy || trajectories.length === 0} onClick={() => void runClustering(true)}>
            {operation === "compare" ? "Comparing…" : "Compare both modes"}
          </button>
        </fieldset>
      </form>

      {trajectories.length === 0 && <p className="pathlet-help">Load trajectories or open a CSV to begin.</p>}
      {error && <p className="trajectory-error" role="alert">{error}</p>}
      {operation && <p className="pathlet-help" role="status">
        {operation === "preview" ? "Reading trajectory CSV…" : operation === "compare"
          ? "Running both modes sequentially…" : "Finding shared paths…"}
      </p>}

      {result && <div className="pathlet-results">
        <p role="status">
          <strong>{result.metrics.shared_pathlet_count} shared {result.metrics.shared_pathlet_count === 1 ? "pathlet" : "pathlets"}</strong>
          {" · "}{result.pathlets.length - result.metrics.shared_pathlet_count} unique portions
        </p>
        <p className="pathlet-help">
          {result.metrics.trajectory_count} trajectories · {result.metrics.epsilon_m} m SSPD
          {" · "}{Math.round(result.metrics.total_runtime_ms)} ms
          {result.metrics.coverage_complete && " · Full coverage"}
        </p>
        <p className="pathlet-help">{result.metrics.use_spatial_index ? "With spatial index" : "Without spatial index"}</p>
        <p className="pathlet-help">Bounding-box filter {result.metrics.use_bounding_box_filter ? "on" : "off"}
          {" · "}{result.metrics.sspd_comparison_count.toLocaleString()} SSPD comparisons</p>
        <label className="pathlet-checkbox">
          <input type="checkbox" checked={showPathlets} disabled={busy}
            onChange={(event) => onShowPathletsChange(event.target.checked)} />
          Show shared paths
        </label>
        <label className="pathlet-checkbox">
          <input type="checkbox" checked={showOriginals} disabled={busy || !showPathlets}
            onChange={(event) => onShowOriginalsChange(event.target.checked)} />
          Overlay original trajectories
        </label>
        <p className="pathlet-help">Click a pathlet for contributor IDs and original point intervals.</p>
      </div>}
      {currentRuns && <PathletTimings runs={currentRuns.runs} useSpatialIndex={useSpatialIndex}
        useBoundingBoxFilter={useBoundingBoxFilter} />}
    </section>
  );
}
