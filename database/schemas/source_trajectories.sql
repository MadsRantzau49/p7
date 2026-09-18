CREATE TABLE source_trajectories (
    source_id CHAR(36) PRIMARY KEY,
    dataset_id INT NOT NULL,

    FOREIGN KEY (dataset_id)
        REFERENCES datasets(dataset_id)
);