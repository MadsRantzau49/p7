import axios from "axios";

const url = "http://127.0.0.1:8000/api/";

export const apiclient = axios.create({baseURL: url})