import type { uniformedTrajectoryResponse } from "../uniformedTrajectoryResponse";
import type { LatLngTuple } from "leaflet";
import type { AreaName, SelectedArea } from "./SelectedArea";
import type { Subtrajectory } from "../subtrajectory";

export interface Props {
  trajectories: uniformedTrajectoryResponse[];
  showTrajectoryDataPoints: boolean;
  cityCenter?: LatLngTuple;
  areas?: Partial<Record<AreaName, SelectedArea>>;
  boxSize?: number;
  onAreaSelect?: (area: SelectedArea) => void;
  subtrajectories?: Subtrajectory[];
  onSubtrajectorySelect?: (id: number) => void;
}
