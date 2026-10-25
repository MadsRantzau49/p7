import { useState } from "react";
import type { Subtrajectory } from "../models/subtrajectory";

interface Props {
  subtrajectories: Subtrajectory[];
  selectedId: number | null;
  showPoints: boolean;
  onSelect: (id: number | null) => void;
  onTogglePoints: () => void;
}

export default function SubtrajectoryResults({ subtrajectories, selectedId, showPoints, onSelect, onTogglePoints }: Props) {
  const [expanded, setExpanded] = useState(false);
  return (
    <section className="trajectory-bottom-bar" aria-label="Retrieved subtrajectories">
      <div className="trajectory-toolbar">
        <button
          type="button"
          className="trajectory-list-toggle"
          onClick={() => setExpanded((previous) => !previous)}
          aria-expanded={expanded}
          aria-controls="loaded-subtrajectories"
        >
          {expanded ? "Hide trajectories" : "Show trajectories"} ({subtrajectories.length})
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
      <div id="loaded-subtrajectories" className="trajectory-list-panel" hidden={!expanded}>
        {subtrajectories.length === 0 ? <p>No subtrajectories loaded yet.</p> : (
          <table className="trajectory-table">
            <caption className="trajectory-table-caption">Select a subtrajectory to show it individually on the map.</caption>
            <thead>
              <tr>
                <th scope="col">Subtrajectory ID</th>
                <th scope="col">Trajectory ID</th>
                <th scope="col">Exit A</th>
                <th scope="col">Entry B</th>
                <th scope="col">Points</th>
              </tr>
            </thead>
            <tbody>
              {subtrajectories.map((subtrajectory) => (
                <tr
                  key={subtrajectory.subtrajectory_id}
                  className={selectedId === subtrajectory.subtrajectory_id ? "trajectory-row-selected" : ""}
                  onClick={() => onSelect(subtrajectory.subtrajectory_id)}
                >
                  <td>
                    <button
                      type="button"
                      className="trajectory-select-button"
                      aria-pressed={selectedId === subtrajectory.subtrajectory_id}
                      onClick={(event) => {
                        event.stopPropagation();
                        onSelect(subtrajectory.subtrajectory_id);
                      }}
                    >{subtrajectory.subtrajectory_id}</button>
                  </td>
                  <td>{subtrajectory.trajectory_id}</td>
                  <td>{subtrajectory.exit_a_time}</td>
                  <td>{subtrajectory.entry_b_time}</td>
                  <td>{subtrajectory.points.length}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
