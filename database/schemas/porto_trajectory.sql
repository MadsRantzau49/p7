CREATE TABLE porto_trajectories (
    source_id CHAR(36) PRIMARY KEY,

    trip_id BIGINT NOT NULL,
    call_type VARCHAR(10),
    origin_call VARCHAR(50),
    origin_stand VARCHAR(50),
    taxi_id BIGINT NOT NULL,
    timestamp BIGINT NOT NULL,
    day_type VARCHAR(10),
    missing_data BOOLEAN NOT NULL,
    polyline JSON NOT NULL,

    FOREIGN KEY (source_id)
        REFERENCES source_trajectories(source_id)
);