import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { getTrajectories, getTrajectoryCities } from "../api/trajectoryAPI";
import type { uniformedTrajectoryResponse } from "../models/uniformedTrajectoryResponse";
import TrajectoryMap from "./trajectoryMap";
import "../css/TrajectoryPage.css";
import type { trajectoryCitites } from "../models/trajectoryCities";


export default function TrajectoryPage() {
  const [cities, setCities] = useState<trajectoryCitites[]>([]);
  const [city, setCity] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
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

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
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
        startDate ? `${startDate}T00:00:00` : undefined,
        endDate ? `${endDate}T23:59:59.999999` : undefined,
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
              <label htmlFor="limit">Maximum trajectories</label>

              <input id="limit" type="number" min="0" step="1" value={limit} onChange={(event) => setLimit(event.target.value)}/>
            </div>

            <button className="trajectory-submit" type="submit" disabled={loading || loadingCities || !city}> {loading ? "Loading..." : "Load trajectories"}</button>
          </fieldset>

          {error && (<p className="trajectory-error" role="alert">{error}</p>)}
        </form>

        <p className="trajectory-description" role="status">{statusMessage}</p>
      </aside>

      <main className="trajectory-workspace">
        <div className="trajectory-map-panel" aria-busy={loading}>
          <TrajectoryMap trajectories={visibleTrajectories} showTrajectoryDataPoints={showTrajectoryDataPoints}/>
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
                      <th scope="col">Taxi ID</th>
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
                          <td>{trajectory.taxi_id}</td>
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