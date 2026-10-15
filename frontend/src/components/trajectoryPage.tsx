import { useEffect, useMemo, useState } from "react";
import type { SubmitEvent } from "react";
import { getTrajectories, getTrajectoryCities } from "../api/trajectoryAPI";
import type { uniformedTrajectoryResponse } from "../models/uniformedTrajectoryResponse";
import TrajectoryMap from "./trajectoryMap";
import TimeRangeSlider from "./timeRangeSlider.tsx";
import DatasetUpload from "./datasetUpload";
import "../css/TrajectoryPage.css";
import type { trajectoryCitites } from "../models/trajectoryCities";
import type { PathletClusteringResult } from "../models/pathlet";
import PathletPanel from "./pathletPanel";


export default function TrajectoryPage() {
  const [cities, setCities] = useState<trajectoryCitites[]>([]);
  const [city, setCity] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const [startTime, setStartTime] = useState("00:00");
  const [endTime, setEndTime] = useState("23:59");

  const [limit, setLimit] = useState("100");

  const [trajectories, setTrajectories] = useState<uniformedTrajectoryResponse[]>([]);
  const [loadedSource, setLoadedSource] = useState("");
  const [pathletResult, setPathletResult] = useState<PathletClusteringResult | null>(null);
  const [pathletBusy, setPathletBusy] = useState(false);
  const [showPathlets, setShowPathlets] = useState(false);
  const [showOriginals, setShowOriginals] = useState(false);

  const [loadingCities, setLoadingCities] = useState(true);
  const [loading, setLoading] = useState(false);
  const [cityError, setCityError] = useState("");
  const [error, setError] = useState("");
  const [hasSearched, setHasSearched] = useState(false);

  const [showTrajectories, setShowTrajectories] = useState(false);
  const [showTrajectoryDataPoints, setShowTrajectoryDataPoints] = useState(false);

  const [selectedTrajectoryId, setSelectedTrajectoryId] =
    useState<number | string | null>(null);

  useEffect(() => {
    let isActive = true;

    async function loadCities() {
      try {
        const availableCities = await getTrajectoryCities();

        if (isActive) {
          setCities(availableCities);
          setCity(availableCities[0]?.name ?? "");
        }
      } catch {
        if (isActive) {
          setCityError("Could not load cities.");
        }
      } finally {
        if (isActive) {
          setLoadingCities(false);
        }
      }
    }

    void loadCities();

    function cleanup() {
      isActive = false;
    }

    return cleanup;
  }, []);

  function handleCityChange(value: string) {
    setCity(value);
    setTrajectories([]);
    setLoadedSource("");
    handlePathletResult(null);
    setSelectedTrajectoryId(null);
    setHasSearched(false);
    setShowTrajectoryDataPoints(false);
    setError("");
  }

  function handlePathletResult(result: PathletClusteringResult | null) {
    setPathletResult(result);
    setShowPathlets(result !== null);
    setShowOriginals(false);
    setShowTrajectoryDataPoints(false);
  }

  function handleLoadedTrajectories(data: uniformedTrajectoryResponse[], source: string) {
    setTrajectories(data);
    setLoadedSource(source);
    setSelectedTrajectoryId(null);
    setHasSearched(true);
    setError("");
    handlePathletResult(null);
  }

  async function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    const requestedLimit = Number(limit);

    if (!city) {
      setError("Please select a city.");
      return;
    }

    if (!Number.isSafeInteger(requestedLimit) || requestedLimit < 1) {
      setError("Enter a positive whole number for the limit.");
      return;
    }

    if (startDate && endDate && startDate > endDate) {
      setError("End date must be on or after start date.");
      return;
    }

    setLoading(true);

    try {
      const data = await getTrajectories(
        city,
        startDate || undefined,
        endDate || undefined,
        startTime ? `${startTime}:00` : undefined,
        endTime ? `${endTime}:59` : undefined,
        requestedLimit
      );

      handleLoadedTrajectories(data, city);
    } catch {
      setError("Could not load trajectories.");
    } finally {
      setLoading(false);
    }
  }

  const visibleTrajectories = useMemo(() => selectedTrajectoryId === null
    ? trajectories : trajectories.filter((trajectory) => trajectory.trajectory_id === selectedTrajectoryId),
    [trajectories, selectedTrajectoryId]);
  const visiblePathlets = useMemo(() => (pathletResult?.pathlets ?? []).filter((pathlet) =>
    selectedTrajectoryId === null || pathlet.trajectory_ids.includes(String(selectedTrajectoryId))),
    [pathletResult, selectedTrajectoryId]);
  const busy = loading || pathletBusy;

  const isSameDay = Boolean(startDate && endDate && startDate === endDate);

  let statusMessage = "Choose your filters to display trajectories.";

  if (loading) {
    statusMessage = "Loading trajectories...";
  } else if (hasSearched && trajectories.length === 0) {
    statusMessage = "No trajectories found for these filters.";
  } else if (hasSearched) {
    statusMessage = `${trajectories.length} trajectories loaded from ${loadedSource}.`;
  }

  return (
    <div className="trajectory-page">
      <aside className="trajectory-sidebar">
        <header>
          <p className="trajectory-eyebrow">TRAJECTORY EXPLORER</p>
          <h1>Find trajectories</h1>
          <p className="trajectory-description">
            Choose a city and refine your search.
          </p>
        </header>

        <form onSubmit={handleSubmit}>
          <fieldset disabled={busy}>
            <div className="trajectory-field">
              <label htmlFor="city">City</label>

              <select
                id="city"
                value={city}
                onChange={(event) =>
                  handleCityChange(event.target.value)
                }
                disabled={loadingCities || cities.length === 0}
                required
              >
                {cities.length === 0 && (<option value=""> {loadingCities ? "Loading cities..." : "No cities available"} </option>)}

                {cities.map((item) => ( <option key={item.dataset_id} value={item.name}> {item.name} </option>))}
              </select>
            </div>

            {cityError && ( <p className="trajectory-error" role="alert"> {cityError} </p>)}

            <div className="trajectory-field">
              <label htmlFor="start-date">Start date</label>
              <input id="start-date" type="date" value={startDate} max={endDate || undefined} onChange={(event) => setStartDate(event.target.value)} />
            </div>

            <div className="trajectory-field">
              <label htmlFor="end-date">End date</label>
              <input id="end-date" type="date" value={endDate} min={startDate || undefined} onChange={(event) => setEndDate(event.target.value)}/>
              <small>Leave dates empty to search all dates.</small>
            </div>

            <div className="trajectory-field">
              <label>Time range</label>

              <TimeRangeSlider
                startTime={startTime}
                endTime={endTime}
                onChange={(
                  newStartTime,
                  newEndTime
                ) => {
                  setStartTime(
                    newStartTime
                  );

                  setEndTime(
                    newEndTime
                  );

                }}
                allowOvernight={!isSameDay}
              />
            </div>


            <div className="trajectory-field">
              <label htmlFor="limit">Maximum trajectories</label>

              <input id="limit" type="number" min="0" step="1" value={limit} onChange={(event) => setLimit(event.target.value)}/>
            </div>

            <button className="trajectory-submit" type="submit" disabled={busy || loadingCities || !city}> {loading ? "Loading..." : "Load trajectories"}</button>
          </fieldset>

          {error && (<p className="trajectory-error" role="alert">{error}</p>)}
        </form>

        <p className="trajectory-description" role="status">{statusMessage}</p>

        <PathletPanel trajectories={trajectories} result={pathletResult} disabled={busy}
          showPathlets={showPathlets} showOriginals={showOriginals}
          onPreviewLoaded={handleLoadedTrajectories} onResultChange={handlePathletResult}
          onBusyChange={setPathletBusy} onShowPathletsChange={setShowPathlets}
          onShowOriginalsChange={setShowOriginals} />

        <DatasetUpload />
      </aside>

      <main className="trajectory-workspace">
        <div className="trajectory-map-panel" aria-busy={busy}>
          <TrajectoryMap trajectories={visibleTrajectories} showTrajectoryDataPoints={showTrajectoryDataPoints}
            pathlets={visiblePathlets} showPathlets={showPathlets} showOriginals={showOriginals} />
        </div>

        <section className="trajectory-bottom-bar">
          <div className="trajectory-toolbar">
            <button type="button" className="trajectory-list-toggle" onClick={() => setShowTrajectories(!showTrajectories)} aria-expanded={showTrajectories} aria-controls="loaded-trajectories">
              {showTrajectories
                ? "Hide trajectories"
                : "Show trajectories"}
              {" "}({trajectories.length})
            </button>

            {selectedTrajectoryId !== null && (
              <button
                type="button"
                className="trajectory-list-toggle"
                onClick={() => {
                  setSelectedTrajectoryId(null);
                  setShowTrajectoryDataPoints(false);
                }}
              >
                Show all trajectories
              </button>
            )}
          </div>

          {showPathlets && <p className="pathlet-filter-note">
            Showing {visiblePathlets.length} pathlets{selectedTrajectoryId !== null
              ? ` involving trajectory ${selectedTrajectoryId}` : " across all loaded trajectories"}.
            {" "}Counts include all contributors from the clustering run.
          </p>}

          <div
            id="loaded-trajectories"
            className="trajectory-list-panel"
            hidden={!showTrajectories}
          >
            {showTrajectories && (
              trajectories.length === 0 ? (
                <p>No trajectories loaded yet.</p>
              ) : (
                <table className="trajectory-table">
                  <caption className="trajectory-table-caption">
                    Click a row to show only that trajectory.
                  </caption>

                  <thead>
                    <tr>
                      <th scope="col">Trajectory ID</th>
                      <th scope="col">Vehicle ID</th>
                      <th scope="col">Vehicle Type</th>
                      <th scope="col">City</th>
                      <th scope="col">Date</th>
                      <th scope="col">Points</th>
                    </tr>
                  </thead>

                  <tbody>
                    {trajectories.map((trajectory) => {
                      const isSelected = selectedTrajectoryId === trajectory.trajectory_id;

                      return (
                        <tr
                          key={trajectory.trajectory_id}
                          className={isSelected ? "trajectory-row-selected": ""}
                          onClick={() => {
                            setSelectedTrajectoryId(trajectory.trajectory_id);
                            setShowTrajectoryDataPoints(false);
                          }}
                        >
                          <td>
                            <button
                              type="button"
                              className="trajectory-select-button"
                              aria-pressed={isSelected}
                              onClick={(event) => {
                                event.stopPropagation();
                                setSelectedTrajectoryId(trajectory.trajectory_id);
                                setShowTrajectoryDataPoints(false);
                              }}
                            >
                              {trajectory.trajectory_id}
                            </button>
                          </td>
                          <td>{trajectory.vehicle_id}</td>
                          <td>{trajectory.vehicle_type ?? "ERROR"}</td>
                          <td>{trajectory.city}</td>
                          <td>{trajectory.trajectory_date}</td>
                          <td>{trajectory.points.length}
                            <button type="button" className="trajectory-points-button" aria-pressed={isSelected && showTrajectoryDataPoints}
                            onClick={(event) => {
                              event.stopPropagation()

                              setSelectedTrajectoryId(trajectory.trajectory_id);
                              setShowTrajectoryDataPoints(!(isSelected && showTrajectoryDataPoints));
                              setShowPathlets(false);
                            }}
                          ></button>
                          {isSelected && showTrajectoryDataPoints ? "Hide data points" : "Show data points"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
