import { useEffect, useState } from "react";
import type { SubmitEvent } from "react";
import axios from "axios";
import { getTimeZones, uploadDataset } from "../api/datasetAPI.ts";
import { getTrajectoryCities } from "../api/trajectoryAPI.ts";
import type { trajectoryCitites } from "../models/trajectoryCities.ts";

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
    const [city, setCity] = useState("");
    const [timeZone, setTimeZone] = useState("");
    const [timeZones, setTimeZones] = useState<string[]>([]);
    const [cities, setCities] = useState<trajectoryCitites[]>([]);
    const [file, setFile] = useState<File | null>(null);
    const [uploading, setUploading] = useState(false);
    const [errors, setErrors] = useState<string[]>([]);
    const [successMessage, setSuccessMessage] = useState("");

    useEffect(() => {
        Promise.all([getTimeZones(), getTrajectoryCities()])
            .then(([zones, existingCities]) => {
                setTimeZones(zones);
                setCities(existingCities);
            })
            .catch(() => setErrors(["Could not load time zones and cities."]));
    }, []);

    // An existing city already has a time zone, so it is shown instead of the user's choice
    const existingCity = cities.find((item) => item.name === city.trim());
    const selectedTimeZone = existingCity ? existingCity.time_zone : timeZone;

    async function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
        event.preventDefault();
        const form = event.currentTarget;
        setErrors([]);
        setSuccessMessage("");

        if (!file) {
            setErrors(["Choose a CSV file."])
            return;
        }

        if (!timeZones.includes(selectedTimeZone)) {
            setErrors(["Choose a time zone from the list."]);
            return;
        }

        setUploading(true);

        try {
            const result = await uploadDataset(name.trim(), city.trim(), selectedTimeZone, file);
            setSuccessMessage(`Dataset "${result.name}" uploaded to ${result.city}`);
            setName("");
            setCity("");
            setTimeZone("");
            setFile(null);
            form.reset();
            getTrajectoryCities().then(setCities).catch(() => setErrors(["Could not reload cities."]));
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
          <label htmlFor="dataset-city">City</label>
          <input id="dataset-city" type="text" list="dataset-city-options" maxLength={100} value={city} onChange={(event) => setCity(event.target.value)} required />
          <datalist id="dataset-city-options">
            {cities.map((item) => (<option key={item.city_id} value={item.name} />))}
          </datalist>
        </div>

        <div className="trajectory-field">
          <label htmlFor="dataset-time-zone">Time zone</label>
          <input id="dataset-time-zone" type="text" list="dataset-time-zone-options" placeholder="Search, e.g. Europe/Copenhagen" value={selectedTimeZone} onChange={(event) => setTimeZone(event.target.value)} disabled={existingCity !== undefined} required />
          <datalist id="dataset-time-zone-options">
            {timeZones.map((zone) => (<option key={zone} value={zone} />))}
          </datalist>
          {existingCity && <p className="trajectory-description">{existingCity.name} already uses this time zone.</p>}
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