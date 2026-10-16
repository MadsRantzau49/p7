import { useEffect, useMemo, useState } from "react";
import type { SubmitEvent } from "react";
import type { LatLngTuple } from "leaflet";
import { isAxiosError } from "axios";
import { getSubpaths } from "../api/subpathAPI";
import type { Subpath } from "../models/subpath";
import { getTrajectories, getTrajectoryCities } from "../api/trajectoryAPI";
import type { uniformedTrajectoryResponse } from "../models/uniformedTrajectoryResponse";
import TrajectoryMap from "./trajectoryMap";
import SubpathResults from "./subpathResults";
import TimeRangeSlider from "./timeRangeSlider.tsx";
import DatasetUpload from "./datasetUpload";
import "../css/TrajectoryPage.css";
import type { trajectoryCitites } from "../models/trajectoryCities";
import type { AreaName, SelectedArea } from "../models/map/SelectedArea";

const PORTO_CENTER: LatLngTuple = [41.1579, -8.6291];
const EMPTY_TRAJECTORIES: uniformedTrajectoryResponse[] = [];

export default function TrajectoryPage() {
  const [sidebarCleared, setSidebarCleared] = useState(false);
  const [explorerCity, setExplorerCity] = useState("");
  const [explorerStartDate, setExplorerStartDate] = useState("");
  const [explorerEndDate, setExplorerEndDate] = useState("");
  const [boxSize, setBoxSize] = useState(2);
  const [activeArea, setActiveArea] = useState<AreaName | null>("A");
  const [areas, setAreas] = useState<Partial<Record<AreaName, SelectedArea>>>({});
  const [subpaths, setSubpaths] = useState<Subpath[]>([]);
  const [selectedSubpathId, setSelectedSubpathId] = useState<number | null>(null);
  const [showSubpathPoints, setShowSubpathPoints] = useState(false);
  const visibleSubpaths = useMemo(() => selectedSubpathId === null
    ? subpaths : subpaths.filter((subpath) => subpath.subpath_id === selectedSubpathId),
  [subpaths, selectedSubpathId]);

  function selectSubpath(id: number | null) {
    setSelectedSubpathId(id);
    setShowSubpathPoints(false);
  }
  const [loadingSubpaths, setLoadingSubpaths] = useState(false);
  const [subpathError, setSubpathError] = useState("");
  const [hasRetrievedSubpaths, setHasRetrievedSubpaths] = useState(false);

  function clearSubpathResults() {
    selectSubpath(null);
    setSubpaths([]);
    setHasRetrievedSubpaths(false);
    setSubpathError("");
  }

  async function handleRetrieveSubpaths(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubpathError("");
    if (!explorerCity || !areas.A || !areas.B || !explorerStartDate || !explorerEndDate) {
      setSubpathError("Choose a city, both dates, and areas A and B.");
      return;
    }
    if (explorerStartDate > explorerEndDate) {
      setSubpathError("End date must be on or after start date.");
      return;
    }
    setLoadingSubpaths(true);
    clearSubpathResults();
    try {
      const data = await getSubpaths(areas.A, areas.B, explorerStartDate, explorerEndDate, boxSize);
      setSubpaths(data);
      setHasRetrievedSubpaths(true);
    } catch (error) {
      const detail = isAxiosError(error) ? error.response?.data?.detail : undefined;
      setSubpathError(typeof detail === "string" ? detail : "Could not retrieve subpaths. Please try again.");
    } finally {
      setLoadingSubpaths(false);
    }
  }

  function handleAreaSelect(area: SelectedArea) {
    if (activeArea === null) return;
    clearSubpathResults();
    setAreas((previous) => ({ ...previous, [activeArea]: area }));
    setActiveArea(!areas[activeArea] && activeArea === "A" && !areas.B ? "B" : null);
  }
  const [cities, setCities] = useState<trajectoryCitites[]>([]);
  const [city, setCity] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const [startTime, setStartTime] = useState("00:00");
  const [endTime, setEndTime] = useState("23:59");

  const [limit, setLimit] = useState("100");

  const [trajectories, setTrajectories] = useState<uniformedTrajectoryResponse[]>([]);

  const [loadingCities, setLoadingCities] = useState(true);
  const [loading, setLoading] = useState(false);
  const [cityError, setCityError] = useState("");
  const [error, setError] = useState("");
  const [hasSearched, setHasSearched] = useState(false);

  const [showTrajectories, setShowTrajectories] = useState(false);
  const [showTrajectoryDataPoints, setShowTrajectoryDataPoints] = useState(false);

  const [selectedTrajectoryId, setSelectedTrajectoryId] =
    useState<number | null>(null);

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
    setSelectedTrajectoryId(null);
    setHasSearched(false);
    setShowTrajectoryDataPoints(false);
    setError("");
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

      setTrajectories(data);
      setSelectedTrajectoryId(null);
      setHasSearched(true);
      setShowTrajectoryDataPoints(false);
    } catch {
      setError("Could not load trajectories.");
    } finally {
      setLoading(false);
    }
  }

  const visibleTrajectories = selectedTrajectoryId === null ? trajectories : trajectories.filter( (trajectory) => trajectory.trajectory_id === selectedTrajectoryId);

  const isSameDay = Boolean(startDate && endDate && startDate === endDate);

  let statusMessage = "Choose your filters to display trajectories.";

  if (loading) {
    statusMessage = "Loading trajectories...";
  } else if (hasSearched && trajectories.length === 0) {
    statusMessage = "No trajectories found for these filters.";
  } else if (hasSearched) {
    statusMessage = `${trajectories.length} trajectories loaded.`;
  }

  return (
    <div className="trajectory-page">
      <aside className="trajectory-sidebar">
        <button
          type="button"
          className="trajectory-list-toggle trajectory-sidebar-clear"
          onClick={() => setSidebarCleared((cleared) => !cleared)}
        >
          {sidebarCleared ? "Restore sidebar" : "Clear sidebar"}
        </button>

        {sidebarCleared ? (
          <form onSubmit={handleRetrieveSubpaths}>
            <fieldset disabled={loadingSubpaths}>
              <div className="trajectory-field">
                <label htmlFor="explorer-city">City</label>
                <select
                  id="explorer-city"
                  value={explorerCity}
                  onChange={(event) => setExplorerCity(event.target.value)}
                >
                  <option value="" disabled>Choose a city</option>
                  <option value="Porto">Porto</option>
                </select>
              </div>
              {explorerCity && (
                <>
                  <div className="trajectory-field">
                    <label htmlFor="explorer-start-date">Start date</label>
                    <input
                      id="explorer-start-date"
                      type="date"
                      required
                      value={explorerStartDate}
                      max={explorerEndDate || undefined}
                      onChange={(event) => {
                        setExplorerStartDate(event.target.value);
                        clearSubpathResults();
                      }}
                    />
                  </div>
                  <div className="trajectory-field">
                    <label htmlFor="explorer-end-date">End date</label>
                    <input
                      id="explorer-end-date"
                      type="date"
                      required
                      value={explorerEndDate}
                      min={explorerStartDate || undefined}
                      onChange={(event) => {
                        setExplorerEndDate(event.target.value);
                        clearSubpathResults();
                      }}
                    />
                  </div>
                  <div className="trajectory-field">
                    <label htmlFor="explorer-box-size">
                      Box size: <output htmlFor="explorer-box-size">{boxSize} m</output>
                    </label>
                    <input
                      id="explorer-box-size"
                      className="trajectory-box-size-slider"
                      type="range"
                      min={2}
                      max={80}
                      step={1}
                      value={boxSize}
                      aria-valuetext={`${boxSize} meters`}
                      onChange={(event) => {
                        setBoxSize(Number(event.target.value));
                        clearSubpathResults();
                      }}
                    />
                    <div className="trajectory-slider-limits" aria-hidden="true">
                      <span>2 m</span>
                      <span>80 m</span>
                    </div>
                  </div>
                  <section className="trajectory-area-selection" aria-label="Map areas">
                    <p role="status">
                      {activeArea === null
                        ? "Select an area below before clicking the map to move it."
                        : `Click the map to ${areas[activeArea] ? "move" : "place"} Area ${activeArea}.`}
                    </p>
                    {(["A", "B"] as const).map((name) => {
                      const area = areas[name];
                      return (
                        <div key={name} className={`trajectory-area-card trajectory-area-${name.toLowerCase()}`}>
                          <button
                            type="button"
                            className="trajectory-list-toggle"
                            aria-pressed={activeArea === name}
                            onClick={() => setActiveArea(name)}
                          >
                            {area ? "Move" : "Select"} Area {name}
                          </button>
                          {area ? (
                            <p>
                              Latitude: {area.latitude.toFixed(6)}<br />
                              Longitude: {area.longitude.toFixed(6)}<br />
                              Size: {boxSize} × {boxSize} m
                            </p>
                          ) : <p>No location selected.</p>}
                        </div>
                      );
                    })}
                  </section>
                  <button
                    className="trajectory-submit"
                    type="submit"
                    disabled={loadingSubpaths || !areas.A || !areas.B || !explorerStartDate || !explorerEndDate || explorerStartDate > explorerEndDate}
                  >
                    {loadingSubpaths ? "Retrieving..." : "Retrieve subpaths"}
                  </button>
                </>
              )}
            </fieldset>
            {subpathError && <p className="trajectory-error" role="alert">{subpathError}</p>}
            <p className="trajectory-description" role="status">
              {loadingSubpaths ? "Retrieving subpaths..." : hasRetrievedSubpaths
                ? subpaths.length === 0 ? "No subpaths found for these areas and dates." : `${subpaths.length} subpaths loaded.`
                : "Choose dates and mark both areas to retrieve subpaths from A to B."}
            </p>
          </form>
        ) : (
          <>
            <header>
              <p className="trajectory-eyebrow">TRAJECTORY EXPLORER</p>
              <h1>Find trajectories</h1>
              <p className="trajectory-description">
                Choose a city and refine your search.
              </p>
            </header>

            <form onSubmit={handleSubmit}>
              <fieldset disabled={loading}>
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

                <button className="trajectory-submit" type="submit" disabled={loading || loadingCities || !city}> {loading ? "Loading..." : "Load trajectories"}</button>
              </fieldset>

              {error && (<p className="trajectory-error" role="alert">{error}</p>)}
            </form>

            <p className="trajectory-description" role="status">{statusMessage}</p>

            <DatasetUpload />
          </>
        )}
      </aside>

      <main className="trajectory-workspace">
        <div className="trajectory-map-panel" aria-busy={sidebarCleared ? loadingSubpaths : loading}>
          <TrajectoryMap
            trajectories={sidebarCleared ? EMPTY_TRAJECTORIES : visibleTrajectories}
            subpaths={sidebarCleared ? visibleSubpaths : undefined}
            onSubpathSelect={sidebarCleared ? selectSubpath : undefined}
            showTrajectoryDataPoints={sidebarCleared ? showSubpathPoints : showTrajectoryDataPoints}
            cityCenter={sidebarCleared && explorerCity === "Porto" ? PORTO_CENTER : undefined}
            areas={sidebarCleared ? areas : undefined}
            boxSize={boxSize}
            onAreaSelect={sidebarCleared && explorerCity && !loadingSubpaths && activeArea !== null ? handleAreaSelect : undefined}
          />
        </div>

        {sidebarCleared && (
          <SubpathResults
            subpaths={subpaths}
            selectedId={selectedSubpathId}
            showPoints={showSubpathPoints}
            onSelect={selectSubpath}
            onTogglePoints={() => setShowSubpathPoints((previous) => !previous)}
          />
        )}

        <section className="trajectory-bottom-bar" hidden={sidebarCleared}>
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
