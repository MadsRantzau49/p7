import { apiclient } from "./apiclient";
import type { Pathlet } from "../models/pathlet";

export const FDS_TIMEOUT_MS = 120_000;

interface RequestOptions {
  signal?: AbortSignal;
  onUploadProgress?: (percentage: number) => void;
}

export async function runFDS(
  file: File,
  epsilon: number,
  maxEntries: number,
  options: RequestOptions = {},
): Promise<Pathlet[]> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("epsilon", String(epsilon));
  formData.append("max_entries", String(maxEntries));

  const response = await apiclient.post<Pathlet[]>("similarity/fds", formData, {
    signal: options.signal,
    timeout: FDS_TIMEOUT_MS,
    onUploadProgress(event) {
      if (event.total) {
        options.onUploadProgress?.(Math.round(event.loaded / event.total * 100));
      }
    },
  });
  return response.data;
}
