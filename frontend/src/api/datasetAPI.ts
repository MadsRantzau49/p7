import { apiclient } from "./apiclient.ts";
import type { datasetUploadResponse } from "../models/datasetUploadResponse.ts";

export async function uploadDataset(name: string, file: File): Promise<datasetUploadResponse> {
    const formData = new FormData();
    formData.append("name", name);
    formData.append("file", file);

    const response = await apiclient.post<datasetUploadResponse>(
        "datasets/upload",
        formData
    );

    return response.data;
}