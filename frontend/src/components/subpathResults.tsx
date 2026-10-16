import { useState } from "react";
import type { Subpath } from "../models/subpath";

interface Props {
  subpaths: Subpath[];
  selectedId: number | null;
  showPoints: boolean;
  onSelect: (id: number | null) => void;
  onTogglePoints: () => void;
}

export default function SubpathResults({ subpaths, selectedId, showPoints, onSelect, onTogglePoints }: Props) {
  const [expanded, setExpanded] = useState(false);
  return (
    <section className="trajectory-bottom-bar" aria-label="Retrieved subpaths">
      <div className="trajectory-toolbar">
        <button
          type="button"
          className="trajectory-list-toggle"
          onClick={() => setExpanded((previous) => !previous)}
          aria-expanded={expanded}
          aria-controls="loaded-subpaths"
        >
          {expanded ? "Hide trajectories" : "Show trajectories"} ({subpaths.length})
        </button>
        {selectedId !== null && (
          <>
            <button type="button" className="trajectory-list-toggle" onClick={() => onSelect(null)}>
              Show all trajectories
            </button>
            <button type="button" className="trajectory-list-toggle" aria-pressed={showPoints} onClick={onTogglePoints}>
              {showPoints ? "Hide data points" : "Show data points"}
            </button>
          </>
        )}
      </div>
      <div id="loaded-subpaths" className="trajectory-list-panel" hidden={!expanded}>
        {subpaths.length === 0 ? <p>No subpaths loaded yet.</p> : (
          <table className="trajectory-table">
            <caption className="trajectory-table-caption">Select a subpath to show it individually on the map.</caption>
            <thead>
              <tr>
                <th scope="col">Subpath ID</th>
                <th scope="col">Trajectory ID</th>
                <th scope="col">Exit A</th>
                <th scope="col">Entry B</th>
                <th scope="col">Points</th>
              </tr>
            </thead>
            <tbody>
              {subpaths.map((subpath) => (
                <tr
                  key={subpath.subpath_id}
                  className={selectedId === subpath.subpath_id ? "trajectory-row-selected" : ""}
                  onClick={() => onSelect(subpath.subpath_id)}
                >
                  <td>
                    <button
                      type="button"
                      className="trajectory-select-button"
                      aria-pressed={selectedId === subpath.subpath_id}
                      onClick={(event) => {
                        event.stopPropagation();
                        onSelect(subpath.subpath_id);
                      }}
                    >{subpath.subpath_id}</button>
                  </td>
                  <td>{subpath.trajectory_id}</td>
                  <td>{subpath.exit_a_time}</td>
                  <td>{subpath.entry_b_time}</td>
                  <td>{subpath.points.length}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
