CREATE TABLE IF NOT EXISTS vehicle_types (
    vehicle_type_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(32) NOT NULL UNIQUE
);

INSERT IGNORE INTO vehicle_types (name) VALUES ('CAR'), ('TAXI'), ('UNKNOWN');

ALTER TABLE uniformed_trajectories
    ADD COLUMN vehicle_type_id INT NULL AFTER city;

UPDATE uniformed_trajectories
    SET vehicle_type_id = (SELECT vehicle_type_id FROM vehicle_types WHERE name = 'TAXI');

ALTER TABLE uniformed_trajectories
    MODIFY vehicle_type_id INT NOT NULL,
    ADD CONSTRAINT fk_uniformed_trajectories_vehicle_type
        FOREIGN KEY (vehicle_type_id) REFERENCES vehicle_types(vehicle_type_id),
    DROP COLUMN vehicle_type;