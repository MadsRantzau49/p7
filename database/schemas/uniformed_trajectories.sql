CREATE TABLE uniformed_trajectories(
    trajectory_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dataset_id INT NOT NULL,
    vehicle_id INT,
    vehicle_type VARCHAR(32) NOT NULL,
    trajectory_date TIMESTAMPTZ,
    city VARCHAR(100) NOT NULL,
    points JSONB NOT NULL,

    FOREIGN KEY (dataset_id) REFERENCES datasets (dataset_id) ON DELETE CASCADE,
    FOREIGN KEY (city) REFERENCES cities (name)
);

CREATE INDEX idx_uniformed_city_date ON uniformed_trajectories (city, trajectory_date);
CREATE INDEX idx_uniformed_date ON uniformed_trajectories (trajectory_date);
CREATE INDEX idx_uniformed_dataset ON uniformed_trajectories (dataset_id);
