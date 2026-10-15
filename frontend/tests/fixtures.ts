import type { PathletClusteringResult } from "../src/models/pathlet";
import type { uniformedTrajectoryResponse } from "../src/models/uniformedTrajectoryResponse";

export const trajectories: uniformedTrajectoryResponse[] = [1, 2].map((id) => ({
  trajectory_id: id, vehicle_id: id, vehicle_type: "CAR", city: "Example", source_id: null,
  trajectory_date: "2024-01-01T00:00:00",
  points: [
    { longitude: 10, latitude: 56, point_timestamp: "2024-01-01T00:00:00" },
    { longitude: 10.1, latitude: 56, point_timestamp: "2024-01-01T00:01:00" },
    { longitude: id === 1 ? 10.2 : 10.1, latitude: id === 1 ? 56 : 56.1,
      point_timestamp: "2024-01-01T00:02:00" },
  ],
}));

function assignment(id: string, start = 0, end = 1) {
  return { trajectory_id: id, start, end, source_rows: [],
    start_timestamp: "2024-01-01T00:00:00", end_timestamp: "2024-01-01T00:01:00" };
}

export const result: PathletClusteringResult = {
  coordinate_order: "latitude,longitude",
  pathlets: [
    { pathlet_id: "shared", coordinates: [[56, 10], [56, 10.1]], count: 2,
      trajectory_ids: ["1", "2"], representative: { trajectory_id: "1", start: 0, end: 1 },
      assignments: [assignment("1"), assignment("2")], max_sspd_m: 0 },
    ...trajectories.map((trajectory) => {
      const id = String(trajectory.trajectory_id);
      return { pathlet_id: `unique-${id}`, coordinates: trajectory.points.slice(1).map((p): [number, number] =>
        [p.latitude, p.longitude]), count: 1, trajectory_ids: [id],
        representative: { trajectory_id: id, start: 1, end: 2 },
        assignments: [assignment(id, 1, 2)], max_sspd_m: 0 };
    }),
  ],
  metrics: { trajectory_count: 2, segment_count: 4, final_pathlet_count: 3, shared_pathlet_count: 1,
    coverage_complete: true, epsilon_m: 2000, total_runtime_ms: 15,
    use_spatial_index: true, use_bounding_box_filter: true, sspd_comparison_count: 3,
    candidate_search_method: "strtree", candidate_discovery_runtime_ms: 5,
    spatial_candidate_pair_count: 3, possible_cross_trajectory_pair_count: 4,
    step_runtime_ms: { "03_spatial_index": 2, "04_nearby_pairs": 3, "05_sspd": 2 } },
};
