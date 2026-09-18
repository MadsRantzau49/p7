CREATE TABLE beijing_trajectories (
    source_id CHAR(36) PRIMARY KEY,

    taxi_id BIGINT NOT NULL,
    points JSON NOT NULL,

    FOREIGN KEY (source_id)
        REFERENCES source_trajectories(source_id)
);