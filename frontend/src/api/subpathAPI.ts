import { apiclient } from "./apiclient";
import type { SelectedArea } from "../models/map/SelectedArea";
import type { Subpath } from "../models/subpath";

export async function getSubpaths(
  areaA: SelectedArea,
  areaB: SelectedArea,
  startDate: string,
  endDate: string,
  boxSize: number,
) {
  const response = await apiclient.get<Subpath[]>("subpaths/get", {
    params: {
      a_longitude: areaA.longitude,
      a_latitude: areaA.latitude,
      b_longitude: areaB.longitude,
      b_latitude: areaB.latitude,
      start_date: startDate,
      end_date: endDate,
      box_half_width_m: boxSize / 2,
    },
  });
  return response.data;
}
