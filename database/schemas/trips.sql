CREATE EXTENSION IF NOT EXISTS mobilitydb CASCADE;

CREATE TABLE trips (
    trajectory_id BIGINT PRIMARY KEY
                   REFERENCES uniformed_trajectories (trajectory_id) ON DELETE CASCADE,
    trip tgeompoint NOT NULL
);

CREATE INDEX idx_trips_trip ON trips USING GIST (trip);