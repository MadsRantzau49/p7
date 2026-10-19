export interface GPSCoordinate {
  latitude: number;
  longitude: number;
}

export interface Pathlet {
  pathlet_id: number;
  count: number;
  trajectories_included: number[];
  points: GPSCoordinate[];
}
