import type { trajectoryPoint } from "./trajectoryPoint";

export interface uniformedTrajectoryResponse {
  trajectory_id: number | string;
  vehicle_id: number;
  vehicle_type: string | null;
  trajectory_date: string;
  city: string | null;
  points: trajectoryPoint[];
  source_id: string | null;
  source_rows?: number[];
}
