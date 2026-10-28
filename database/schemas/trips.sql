CREATE EXTENSION IF NOT EXISTS mobilitydb CASCADE;

CREATE TABLE trips (
    trajectory_id BIGINT PRIMARY KEY
                   REFERENCES cleaned_uniformed_trajectories (trajectory_id) ON DELETE CASCADE,
    trip tgeompoint NOT NULL
);

CREATE INDEX idx_trips_trip ON trips USING SPGIST (trip);