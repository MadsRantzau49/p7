import axios from "axios";
import { apiclient } from "./apiclient";
import type { PathletClusteringResult } from "../models/pathlet";
import type { uniformedTrajectoryResponse } from "../models/uniformedTrajectoryResponse";

export async function clusterTrajectories(
  trajectories: uniformedTrajectoryResponse[],
  epsilonM: number,
  signal?: AbortSignal,
): Promise<PathletClusteringResult> {
  const response = await apiclient.post<PathletClusteringResult>(
    "trajectories/pathlets",
    {
      epsilon_m: epsilonM,
      trajectories: trajectories.map(({ trajectory_id, points, source_rows }) => ({
        trajectory_id,
        points,
        source_rows,
      })),
    },
    { signal },
  );
  return response.data;
}

export async function previewTrajectoryCsv(
  file: File,
  signal?: AbortSignal,
): Promise<uniformedTrajectoryResponse[]> {
  const body = new FormData();
  body.append("file", file);
  const response = await apiclient.post<uniformedTrajectoryResponse[]>(
    "trajectories/preview", body, { signal },
  );
  return response.data;
}

export function getPathletError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail: unknown = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail.map((item) => `${item.loc?.slice(1).join(" → ") ?? "Input"}: ${item.msg}`).join("; ");
    }
  }
  return "Could not process trajectories. Check the backend connection and try again.";
}
