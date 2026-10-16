import type { trajectoryPoint } from "./trajectoryPoint";

export interface Subpath {
  subpath_id: number;
  trajectory_id: number;
  exit_a_time: string;
  entry_b_time: string;
  points: trajectoryPoint[];
}
