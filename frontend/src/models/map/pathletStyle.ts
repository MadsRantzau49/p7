import type { PathOptions } from "leaflet";

export function pathletStyle(count: number): PathOptions {
  return {
    color: count === 1 ? "#64748b" : count === 2 ? "#0284c7" : count <= 4 ? "#0d9488" : "#7c3aed",
    weight: Math.min(14, 2 + 2 * Math.sqrt(count)),
    opacity: count === 1 ? 0.7 : 0.95,
    lineCap: "round",
  };
}

export function trajectoryHue(id: number | string): number {
  if (typeof id === "number") return (id * 137.508) % 360;
  // String CSV IDs have no numeric database ID; hash them consistently.
  let hash = 0;
  for (const character of id) hash = ((hash * 31) + character.charCodeAt(0)) >>> 0;
  return hash % 360;
}
