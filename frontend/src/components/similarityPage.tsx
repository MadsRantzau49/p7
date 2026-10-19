import { useMemo, useRef, useState } from "react";
import type { SubmitEvent } from "react";
import { isAxiosError } from "axios";
import { FDS_TIMEOUT_MS, runFDS } from "../api/similarityAPI";
import type { Pathlet } from "../models/pathlet";
import type { uniformedTrajectoryResponse } from "../models/uniformedTrajectoryResponse";
import TrajectoryMap from "./trajectoryMap";

const EMPTY_TRAJECTORIES: uniformedTrajectoryResponse[] = [];

function errorMessages(error: unknown): string[] {
  if (isAxiosError(error)) {
    if (error.code === "ERR_CANCELED") return ["FDS request cancelled. You can retry the upload."];
    if (error.code === "ECONNABORTED" || error.code === "ETIMEDOUT") {
      return [`No FDS response after ${FDS_TIMEOUT_MS / 1000} seconds. Check the backend logs and retry.`];
    }
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return [detail];
    if (Array.isArray(detail)) {
      return detail.map((item) => item.line !== undefined
        ? `Line ${item.line}: ${item.message}`
        : item.msg ?? "Invalid request.");
    }
  }
  return ["Could not run FDS. Check the backend connection and try again."];
}

export default function SimilarityPage({ onBack }: { onBack: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [epsilon, setEpsilon] = useState("2000");
  const [maxEntries, setMaxEntries] = useState("4");
  const [pathlets, setPathlets] = useState<Pathlet[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [showPoints, setShowPoints] = useState(false);
  const [running, setRunning] = useState(false);
  const [hasRun, setHasRun] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const requestController = useRef<AbortController | null>(null);
  const visiblePathlets = useMemo(() => selectedId === null
    ? pathlets : pathlets.filter((pathlet) => pathlet.pathlet_id === selectedId), [pathlets, selectedId]);

  function clearResults() {
    setPathlets([]);
    setSelectedId(null);
    setShowPoints(false);
    setHasRun(false);
    setErrors([]);
    setUploadProgress(0);
    setElapsedSeconds(0);
  }

  async function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrors([]);
    const distance = Number(epsilon);
    const entries = Number(maxEntries);
    if (!file) {
      setErrors(["Choose a CSV file."]);
      return;
    }
    if (!epsilon.trim() || !Number.isFinite(distance) || distance < 0) {
      setErrors(["Epsilon must be a finite distance of zero or more meters."]);
      return;
    }
    if (!maxEntries.trim() || !Number.isSafeInteger(entries) || entries < 2) {
      setErrors(["Maximum R-tree entries must be a whole number of at least 2."]);
      return;
    }

    clearResults();
    setRunning(true);
    const controller = new AbortController();
    requestController.current = controller;
    const started = performance.now();
    const timer = window.setInterval(() => {
      setElapsedSeconds(Math.floor((performance.now() - started) / 1000));
    }, 1000);
    try {
      const result = await runFDS(file, distance, entries, {
        signal: controller.signal,
        onUploadProgress: setUploadProgress,
      });
      setPathlets(result);
      setHasRun(true);
    } catch (error) {
      setErrors(errorMessages(error));
    } finally {
      window.clearInterval(timer);
      requestController.current = null;
      setRunning(false);
    }
  }

  return (
    <div className="trajectory-page">
      <aside className="trajectory-sidebar">
        <button type="button" className="trajectory-list-toggle trajectory-sidebar-clear"
          onClick={onBack} disabled={running}>
          Back to trajectories
        </button>
        <header>
          <p className="trajectory-eyebrow">SIMILARITY EXPLORER</p>
          <h1>Run FDS</h1>
          <p className="trajectory-description">
            Upload a CSV and compare its routes. Each CSV route becomes a complete subpath,
            using the same conversion as debug_fds.
          </p>
        </header>
        <form onSubmit={handleSubmit}>
          <fieldset disabled={running}>
            <div className="trajectory-field">
              <label htmlFor="fds-file">CSV file</label>
              <input id="fds-file" type="file" accept=".csv,text/csv" required onChange={(event) => {
                setFile(event.target.files?.[0] ?? null);
                clearResults();
              }} />
              <small>Use the trajectory builder CSV format. Vehicle type is CAR, TAXI, or UNKNOWN.</small>
            </div>
            <div className="trajectory-field">
              <label htmlFor="fds-epsilon">Epsilon (meters)</label>
              <input id="fds-epsilon" type="number" min="0" step="any" required value={epsilon}
                onChange={(event) => { setEpsilon(event.target.value); clearResults(); }} />
              <small>Maximum SSPD distance for matching segments and extended paths.</small>
            </div>
            <div className="trajectory-field">
              <label htmlFor="fds-max-entries">Maximum R-tree entries</label>
              <input id="fds-max-entries" type="number" min="2" step="1" required value={maxEntries}
                onChange={(event) => { setMaxEntries(event.target.value); clearResults(); }} />
            </div>
            <button className="trajectory-submit" type="submit" disabled={running || !file}>
              {running ? "Running FDS..." : "Run FDS"}
            </button>
          </fieldset>
        </form>
        {running && (
          <button type="button" className="trajectory-list-toggle similarity-cancel"
            onClick={() => requestController.current?.abort()}>
            Cancel request
          </button>
        )}
        {errors.length > 0 && (
          <div className="trajectory-error" role="alert">
            <ul>{errors.map((message, index) => <li key={index}>{message}</li>)}</ul>
          </div>
        )}
        <p className="trajectory-description" role="status">
          {running ? `${uploadProgress < 100
            ? `Uploading CSV: ${uploadProgress}%`
            : "CSV uploaded. Waiting for FDS results"} (${elapsedSeconds}s)`
            : hasRun ? `${pathlets.length} GPS pathlets returned. Select one on the map or in the results.`
              : "Choose a CSV file and run FDS to visualize the resulting pathlets."}
        </p>
      </aside>
      <main className="trajectory-workspace">
        <div className="trajectory-map-panel" aria-busy={running}>
          <TrajectoryMap trajectories={EMPTY_TRAJECTORIES} showTrajectoryDataPoints={showPoints}
            pathlets={visiblePathlets} onPathletSelect={setSelectedId} />
        </div>
        {hasRun && (
          <section className="trajectory-bottom-bar" aria-label="FDS pathlets">
            <div className="similarity-toolbar">
              <strong>{pathlets.length} pathlets</strong>
              {selectedId !== null && (
                <button type="button" className="trajectory-list-toggle" onClick={() => setSelectedId(null)}>
                  Show all pathlets
                </button>
              )}
              <label>
                <input type="checkbox" checked={showPoints}
                  onChange={(event) => setShowPoints(event.target.checked)} /> Show pathlet points
              </label>
            </div>
            <div className="trajectory-list-panel">
              {pathlets.length === 0 ? <p>No pathlets were produced for this file.</p> : (
                <table className="trajectory-table">
                  <caption className="trajectory-table-caption">Select a pathlet to show it individually on the map.</caption>
                  <thead>
                    <tr><th scope="col">Pathlet</th><th scope="col">Support</th>
                      <th scope="col">Trajectory IDs</th><th scope="col">Points</th></tr>
                  </thead>
                  <tbody>
                    {pathlets.map((pathlet) => (
                      <tr key={pathlet.pathlet_id} onClick={() => setSelectedId(pathlet.pathlet_id)}
                        className={selectedId === pathlet.pathlet_id ? "trajectory-row-selected" : ""}>
                        <td>
                          <button type="button" className="trajectory-select-button"
                            aria-label={`Show pathlet ${pathlet.pathlet_id}`} aria-pressed={selectedId === pathlet.pathlet_id}
                            onClick={(event) => { event.stopPropagation(); setSelectedId(pathlet.pathlet_id); }}>
                            {pathlet.pathlet_id}
                          </button>
                        </td>
                        <td>{pathlet.count}</td>
                        <td className="similarity-trajectory-ids">{pathlet.trajectories_included.join(", ")}</td>
                        <td>{pathlet.points.length}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
