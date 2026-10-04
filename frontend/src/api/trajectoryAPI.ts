import { apiclient } from "../api/apiclient";
import type { uniformedTrajectoryResponse } from "../models/uniformedTrajectoryResponse";
import type { trajectoryCitites } from "../models/trajectoryCities";

export async function getTrajectories(city: string, startDate?: string, endDate?: string, startTime?: string,
  endTime?: string, limit?: number){
    const response = await apiclient.get<uniformedTrajectoryResponse[]>(
        "trajectories/get",
        {
            params: {
                city,
                start_date: startDate,
                end_date: endDate,
                start_time: startTime,
                end_time: endTime,
                limit: limit
            },
        }
    );
    return response.data;
}

export async function getTrajectoryCities(){
    const response = await apiclient.get<trajectoryCitites[]>(
        "trajectories/get/cities"
    )

    return response.data
}

