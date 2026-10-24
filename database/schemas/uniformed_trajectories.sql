CREATE TABLE uniformed_trajectories(
    trajectory_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    vehicle_id INT,
    trajectory_date TIMESTAMPTZ,
    city VARCHAR(100) NOT NULL,
    vehicle_type_id INT NOT NULL,
    points JSONB NOT NULL,
    source_id CHAR(36) NOT NULL,

    FOREIGN KEY (vehicle_type_id) REFERENCES vehicle_types(vehicle_type_id),
    FOREIGN KEY (source_id) REFERENCES source_trajectories(source_id)
);

CREATE INDEX idx_uniformed_city_date ON uniformed_trajectories (city, trajectory_date);
CREATE INDEX idx_uniformed_date ON uniformed_trajectories (trajectory_date);
