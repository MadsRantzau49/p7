import { useEffect, useMemo, useState } from "react";
import type { SubmitEvent } from "react";
import type { LatLngTuple } from "leaflet";
import { isAxiosError } from "axios";
import { getSubtrajectories } from "../api/subtrajectoryAPI";
import type { Subtrajectory } from "../models/subtrajectory";
import { getTrajectories, getTrajectoryCities } from "../api/trajectoryAPI";
import type { uniformedTrajectoryResponse } from "../models/uniformedTrajectoryResponse";
import TrajectoryMap from "./trajectoryMap";
import SubtrajectoryResults from "./subtrajectoryResults";
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
  const [subtrajectories, setSubtrajectories] = useState<Subtrajectory[]>([]);
  const [selectedSubtrajectoryId, setSelectedSubtrajectoryId] = useState<number | null>(null);
  const [showSubtrajectoryPoints, setShowSubtrajectoryPoints] = useState(false);
  const visibleSubtrajectories = useMemo(() => selectedSubtrajectoryId === null
    ? subtrajectories : subtrajectories.filter((subtrajectory) => subtrajectory.subtrajectory_id === selectedSubtrajectoryId),
  [subtrajectories, selectedSubtrajectoryId]);

  function selectSubtrajectory(id: number | null) {
    setSelectedSubtrajectoryId(id);
    setShowSubtrajectoryPoints(false);
  }
  const [loadingSubtrajectories, setLoadingSubtrajectories] = useState(false);
  const [subtrajectoryError, setSubtrajectoryError] = useState("");
  const [hasRetrievedSubtrajectories, setHasRetrievedSubtrajectories] = useState(false);

  function clearSubtrajectoryResults() {
    selectSubtrajectory(null);
    setSubtrajectories([]);
    setHasRetrievedSubtrajectories(false);
    setSubtrajectoryError("");
  }

  async function handleRetrieveSubtrajectories(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubtrajectoryError("");
    if (!explorerCity || !areas.A || !areas.B || !explorerStartDate || !explorerEndDate) {
      setSubtrajectoryError("Choose a city, both dates, and areas A and B.");
      return;
    }
    if (explorerStartDate > explorerEndDate) {
      setSubtrajectoryError("End date must be on or after start date.");
      return;
    }
    setLoadingSubtrajectories(true);
    clearSubtrajectoryResults();
    try {
      const data = await getSubtrajectories(areas.A, areas.B, explorerStartDate, explorerEndDate, boxSize);
      setSubtrajectories(data);
      setHasRetrievedSubtrajectories(true);
    } catch (error) {
      const detail = isAxiosError(error) ? error.response?.data?.detail : undefined;
      setSubtrajectoryError(typeof detail === "string" ? detail : "Could not retrieve subtrajectories. Please try again.");
    } finally {
      setLoadingSubtrajectories(false);
    }
  }

  function handleAreaSelect(area: SelectedArea) {
    if (activeArea === null) return;
    clearSubtrajectoryResults();
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
          <form onSubmit={handleRetrieveSubtrajectories}>
            <fieldset disabled={loadingSubtrajectories}>
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
                        clearSubtrajectoryResults();
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
                        clearSubtrajectoryResults();
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
                        clearSubtrajectoryResults();
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
                    disabled={loadingSubtrajectories || !areas.A || !areas.B || !explorerStartDate || !explorerEndDate || explorerStartDate > explorerEndDate}
                  >
                    {loadingSubtrajectories ? "Retrieving..." : "Retrieve subtrajectories"}
                  </button>
                </>
              )}
            </fieldset>
            {subtrajectoryError && <p className="trajectory-error" role="alert">{subtrajectoryError}</p>}
            <p className="trajectory-description" role="status">
              {loadingSubtrajectories ? "Retrieving subtrajectories..." : hasRetrievedSubtrajectories
                ? subtrajectories.length === 0 ? "No subtrajectories found for these areas and dates." : `${subtrajectories.length} subtrajectories loaded.`
                : "Choose dates and mark both areas to retrieve subtrajectories from A to B."}
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

                    {cities.map((item) => ( <option key={item.city_id} value={item.name}> {item.name} </option>))}
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
        <div className="trajectory-map-panel" aria-busy={sidebarCleared ? loadingSubtrajectories : loading}>
          <TrajectoryMap
            trajectories={sidebarCleared ? EMPTY_TRAJECTORIES : visibleTrajectories}
            subtrajectories={sidebarCleared ? visibleSubtrajectories : undefined}
            onSubtrajectorySelect={sidebarCleared ? selectSubtrajectory : undefined}
            showTrajectoryDataPoints={sidebarCleared ? showSubtrajectoryPoints : showTrajectoryDataPoints}
            cityCenter={sidebarCleared && explorerCity === "Porto" ? PORTO_CENTER : undefined}
            areas={sidebarCleared ? areas : undefined}
            boxSize={boxSize}
            onAreaSelect={sidebarCleared && explorerCity && !loadingSubtrajectories && activeArea !== null ? handleAreaSelect : undefined}
          />
        </div>

        {sidebarCleared && (
          <SubtrajectoryResults
            subtrajectories={subtrajectories}
            selectedId={selectedSubtrajectoryId}
            showPoints={showSubtrajectoryPoints}
            onSelect={selectSubtrajectory}
            onTogglePoints={() => setShowSubtrajectoryPoints((previous) => !previous)}
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
