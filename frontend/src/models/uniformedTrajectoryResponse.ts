import type { trajectoryPoint } from "./trajectoryPoint";

export interface uniformedTrajectoryResponse{
    trajectory_id: number;
    taxi_id: number;
    trajectory_date: string;
    city: string;
    points: trajectoryPoint[]
}