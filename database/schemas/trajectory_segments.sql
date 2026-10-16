CREATE TABLE trajectory_segments(
    trajectory_id BIGINT NOT NULL,
    segment_index INT NOT NULL,
    path LINESTRING NOT NULL SRID 4326,
    start_time datetime NOT NULL,
    end_time datetime NOT NULL,

    min_longitude DOUBLE GENERATED ALWAYS AS
        (LEAST(ST_Longitude(ST_StartPoint(path)), ST_Longitude(ST_EndPoint(path)))) VIRTUAL,
    max_longitude DOUBLE GENERATED ALWAYS AS
        (GREATEST(ST_Longitude(ST_StartPoint(path)), ST_Longitude(ST_EndPoint(path)))) VIRTUAL,
    min_latitude DOUBLE GENERATED ALWAYS AS
        (LEAST(ST_Latitude(ST_StartPoint(path)), ST_Latitude(ST_EndPoint(path)))) VIRTUAL,
    max_latitude DOUBLE GENERATED ALWAYS AS
        (GREATEST(ST_Latitude(ST_StartPoint(path)), ST_Latitude(ST_EndPoint(path)))) VIRTUAL,

    PRIMARY KEY (trajectory_id, segment_index),

    SPATIAL INDEX idx_segment_path (path),
    INDEX idx_segment_start_time (start_time),
    INDEX idx_segment_time_bounds (start_time, min_longitude, max_longitude, min_latitude, max_latitude),

    FOREIGN KEY (trajectory_id) REFERENCES cleaned_uniformed_trajectories (trajectory_id)
);