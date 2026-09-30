import { useState } from "react";
import type { SubmitEvent } from "react";
import axios from "axios";
import { uploadDataset } from "../api/datasetAPI.ts";

function getErrorMessages(error: unknown): string[] {
    if (axios.isAxiosError(error) && error.response) {
        const detail = error.response.data?.detail;

        if (typeof detail === "string") {
            return [detail]
        }

        if (Array.isArray(detail)) {
            return detail.map((item) =>
                item.line !== undefined ? `Line ${item.line}: ${item.message}` : item.msg
            );
        }
    }

    return ["Upload failed."];
}

export default function DatasetUpload() {
    const [name, setName] = useState("");
    const [file, setFile] = useState<File | null>(null);
    const [uploading, setUploading] = useState(false);
    const [errors, setErrors] = useState<string[]>([]);
    const [successMessage, setSuccessMessage] = useState("");

    async function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
        event.preventDefault();
        const form = event.currentTarget;
        setErrors([]);
        setSuccessMessage("");

        if (!file) {
            setErrors(["Choose a CSV file."])
            return;
        }

        setUploading(true);

        try {
            const result = await uploadDataset(name.trim(), file);
            setSuccessMessage(`Dataset "${result.name}" uploaded`);
            setName("");
            setFile(null);
            form.reset();
        } catch (error) {
            setErrors(getErrorMessages(error));
        } finally {
            setUploading(false);
        }
    }

    return (
    <form onSubmit={handleSubmit}>
      <h2>Upload dataset</h2>

      <fieldset disabled={uploading}>
        <div className="trajectory-field">
          <label htmlFor="dataset-name">Dataset name</label>
          <input id="dataset-name" type="text" maxLength={50} value={name} onChange={(event) => setName(event.target.value)} required />
        </div>

        <div className="trajectory-field">
          <label htmlFor="dataset-file">CSV file</label>
          <input id="dataset-file" type="file" accept=".csv,text/csv" onChange={(event) => setFile(event.target.files?.[0] ?? null)} required />
        </div>

        <button className="trajectory-submit" type="submit">{uploading ? "Uploading..." : "Upload"}</button>
      </fieldset>

      {successMessage && <p className="trajectory-description" role="status">{successMessage}</p>}

      {errors.length > 0 && (
        <div className="trajectory-error" role="alert">
          <ul>
            {errors.map((message, index) => (<li key={index}>{message}</li>))}
          </ul>
        </div>
      )}
    </form>
  );
}