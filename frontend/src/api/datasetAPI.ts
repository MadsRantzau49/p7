import { apiclient } from "./apiclient.ts";
import type { datasetUploadResponse } from "../models/datasetUploadResponse.ts";

export async function uploadDataset(name: string, city: string, timeZone: string, file: File): Promise<datasetUploadResponse> {
    const formData = new FormData();
    formData.append("name", name);
    formData.append("city", city);
    formData.append("time_zone", timeZone);
    formData.append("file", file);

    const response = await apiclient.post<datasetUploadResponse>(
        "datasets/upload",
        formData
    );

    return response.data;
}

export async function getTimeZones(): Promise<string[]> {
    const response = await apiclient.get<string[]>("datasets/time-zones");

    return response.data;
}