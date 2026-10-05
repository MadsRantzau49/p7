CREATE TABLE trajectory_segments(
    trajectory_id BIGINT NOT NULL,
    segment_index INT NOT NULL,
    path LINESTRING NOT NULL SRID 4326,
    start_time datetime NOT NULL,
    end_time datetime NOT NULL,

    PRIMARY KEY (trajectory_id, segment_index),

    SPATIAL INDEX idx_segment_path (path), 
    INDEX idx_segment_start_time (start_time),

    FOREIGN KEY (trajectory_id) REFERENCES cleaned_uniformed_trajectories (trajectory_id)
);