import { useEffect, useMemo } from "react";
import { MapContainer, TileLayer, Polyline, CircleMarker, Marker, Popup, useMap} from "react-leaflet";
import { divIcon, latLngBounds } from "leaflet";
import type { LatLngTuple } from "leaflet";
import type { Props } from "../models/map/Props"
import type { MapViewProps } from "../models/map/MapViewProps";
import "leaflet/dist/leaflet.css";
import "../css/trajectoryMap.css"

function MapView({ positions }: MapViewProps) {
  const map = useMap();

  useEffect(() => {
    if (positions.length === 0) return;

    map.fitBounds(latLngBounds(positions), {padding: [30, 30],maxZoom: 15});
  }, [positions, map]);

  useEffect(() => {
    const observer = new ResizeObserver(() => {map.invalidateSize();});

    observer.observe(map.getContainer());

    return () => observer.disconnect();
  }, [map]);

  return null;

  
}

export default function TrajectoryMap({ trajectories, showTrajectoryDataPoints }: Props) {
  const routes = useMemo(() =>
      trajectories.map((trajectory) => {
        const hue = (trajectory.trajectory_id * 137.508) % 360;
        const color = `hsl(${hue}, 75%, 40%)`;

        const positions: LatLngTuple[] = trajectory.points.map(
          (point) => [point.latitude, point.longitude]
        );

        const endIcon = divIcon({
          className: "trajectory-end-icon",
          html: `<span style="background-color: ${color}"></span>`,
          iconSize: [16, 16],
          iconAnchor: [8, 8],
          popupAnchor: [0, -10],
        });

        return { trajectory, positions, color, endIcon };
      }),
    [trajectories]
  );

  const allPositions = useMemo(() => routes.flatMap((route) => route.positions), [routes]);

  return (
    <div className="trajectory-map-wrapper">
      <MapContainer
        className="trajectory-map"
        center={[0, 0]}
        zoom={2}
        scrollWheelZoom
        preferCanvas
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          maxZoom={19}
        />

        <MapView positions={allPositions} />

        {routes.map(({ trajectory, positions, color }) =>
          positions.length > 1 ? (
            <Polyline
              key={`path-${trajectory.trajectory_id}`}
              positions={positions}
              pathOptions={{ color, weight: 3, opacity: 0.85 }}
            >
              <Popup>
                <strong>Trajectory {trajectory.trajectory_id}</strong>
                <br />
                Taxi {trajectory.taxi_id}
                <br />
                {trajectory.city}
              </Popup>
            </Polyline>
          ) : null
        )}

        {/* Show each recorded coordinate as a circle. */}
        {showTrajectoryDataPoints &&
          routes.map(({ trajectory, positions, color }) =>
            positions.map((position, index) => (
              <CircleMarker
                key={`point-${trajectory.trajectory_id}-${index}`}
                center={position}
                radius={4}
                pathOptions={{color, weight: 2, fillColor: "#ffffff", fillOpacity: 1}}
              >
                <Popup>
                  <strong>Point {index + 1}</strong>
                  <br />
                  Trajectory {trajectory.trajectory_id}
                  <br />
                  Latitude: {position[0]}
                  <br />
                  Longitude: {position[1]}
                  <br />
                  Date time: {trajectory.points[index]?.point_timestamp}
                  <br />
                  {position[2]}
                </Popup>
              </CircleMarker>
            ))
          )}

        {/* This creates the map circle to indicate the start of a trajectory */}
        {routes.map(({ trajectory, positions, color }) => {
          const start = positions[0];
          if (!start) return null;

          return (
            <CircleMarker
              key={`start-${trajectory.trajectory_id}`}
              center={start}
              radius={7}
              pathOptions={{
                color: "#ffffff",
                weight: 2,
                fillColor: color,
                fillOpacity: 1,
              }}
            >
              <Popup>
                <strong>Start</strong>
                <br />
                Trajectory {trajectory.trajectory_id}
                <br />
                {trajectory.points[0]?.point_timestamp}
              </Popup>
            </CircleMarker>
          );
        })}

        {/* This creates the map square to indicate the end of a trajectory */}
        {routes.map(({ trajectory, positions, endIcon }) => {
          const end = positions[positions.length - 1];
          if (!end) return null;

          return (
            <Marker
              key={`end-${trajectory.trajectory_id}`}
              position={end}
              icon={endIcon}
            >
              <Popup>
                <strong>End</strong>
                <br />
                Trajectory {trajectory.trajectory_id}
                <br />
                {trajectory.points[trajectory.points.length - 1]?.point_timestamp}
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>

      <div className="trajectory-map-legend">
        <span>
          <i className="legend-start" aria-hidden="true" />
          Start
        </span>
        <span>
          <i className="legend-end" aria-hidden="true" />
          End
        </span>
      </div>
    </div>
  );
}