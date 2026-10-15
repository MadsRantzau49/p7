import { useMemo } from "react";
import { Pane, Polyline, Popup, Tooltip } from "react-leaflet";
import type { Pathlet } from "../models/pathlet";
import { pathletStyle } from "../models/map/pathletStyle";

export default function PathletLayer({ pathlets }: { pathlets: Pathlet[] }) {
  const ordered = useMemo(() => [...pathlets].sort((a, b) =>
    a.count - b.count || a.pathlet_id.localeCompare(b.pathlet_id)), [pathlets]);

  return <Pane name="shared-pathlets" style={{ zIndex: 450 }}>
    {ordered.map((pathlet) => <Polyline key={pathlet.pathlet_id} positions={pathlet.coordinates}
      pathOptions={pathletStyle(pathlet.count)}>
      <Tooltip sticky>{pathlet.count} {pathlet.count === 1 ? "trajectory · unique portion" : "trajectories"}</Tooltip>
      <Popup maxWidth={440}>
        <div className="pathlet-popup">
          <strong>{pathlet.count} {pathlet.count === 1 ? "trajectory" : "trajectories"}</strong>
          <p>{pathlet.count === 1 ? "Unique portion" : "Shared corridor"} · {pathlet.pathlet_id}</p>
          <p>Representative: {pathlet.representative.trajectory_id}<br />
            Maximum SSPD: {pathlet.max_sspd_m.toFixed(2)} m</p>
          <table>
            <caption>Contributing original portions (zero-based point indices)</caption>
            <thead><tr><th>Trajectory</th><th>Point interval</th></tr></thead>
            <tbody>{pathlet.assignments.map((assignment) => <tr key={assignment.trajectory_id}>
              <td>{assignment.trajectory_id}</td>
              <td title={`${assignment.start} → ${assignment.end}`}>
                {assignment.start.toFixed(3)} → {assignment.end.toFixed(3)}
                {assignment.start_timestamp && <small>
                  {assignment.start_timestamp.replace("T", " ")}<br />
                  → {assignment.end_timestamp?.replace("T", " ")}
                </small>}
                {assignment.source_rows.length > 0 && <small>CSV rows: {assignment.source_rows.join(", ")}</small>}
              </td>
            </tr>)}</tbody>
          </table>
        </div>
      </Popup>
    </Polyline>)}
  </Pane>;
}
