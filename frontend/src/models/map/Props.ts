import type { uniformedTrajectoryResponse } from "../uniformedTrajectoryResponse";
import type { Pathlet } from "../pathlet";

export interface Props {
  trajectories: uniformedTrajectoryResponse[];
  showTrajectoryDataPoints: boolean;
  pathlets?: Pathlet[];
  showPathlets?: boolean;
  showOriginals?: boolean;
}
