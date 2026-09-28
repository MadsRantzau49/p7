import type { trajectoryPoint } from "./trajectoryPoint";

export interface uniformedTrajectoryResponse {
  trajectory_id: number;
  vehicle_id: number;
  vehicle_type: string | null;
  trajectory_date: string;
  city: string;
  points: trajectoryPoint[];
  source_id: string;
}