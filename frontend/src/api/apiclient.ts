import axios from "axios";

const api_url = import.meta.env.VITE_BACKEND_API_PATH || "/api/"

export const apiclient = axios.create({baseURL: api_url})
