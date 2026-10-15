export interface PathletAssignment {
  trajectory_id: string;
  start: number;
  end: number;
  start_timestamp: string | null;
  end_timestamp: string | null;
  source_rows: number[];
}

export interface Pathlet {
  pathlet_id: string;
  coordinates: [number, number][];
  count: number;
  trajectory_ids: string[];
  representative: { trajectory_id: string; start: number; end: number };
  assignments: PathletAssignment[];
  max_sspd_m: number;
}

export interface PathletClusteringResult {
  coordinate_order: "latitude,longitude";
  pathlets: Pathlet[];
  metrics: {
    trajectory_count: number;
    segment_count: number;
    final_pathlet_count: number;
    shared_pathlet_count: number;
    coverage_complete: boolean;
    epsilon_m: number;
    total_runtime_ms: number;
    step_runtime_ms: Record<string, number>;
  };
}
