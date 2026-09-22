CREATE TABLE uniformed_trajectories(
    trajectory_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    vehicle_id INT,
    trajectory_date DATETIME,
    city VARCHAR(100) NOT NULL,
    vehicle_type ENUM('CAR', 'UNKNOWN') NOT NULL DEFAULT 'CAR',
    points JSON NOT NULL,

    source_id CHAR(36) NOT NULL,

    FOREIGN KEY (source_id) REFERENCES source_trajectories(source_id),
    INDEX idx_city_date (city, trajectory_date),
    INDEX idx_trajectory_date (trajectory_date)
);