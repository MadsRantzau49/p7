CREATE TABLE vehicle_types (
    vehicle_type_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(32) NOT NULL UNIQUE
);

INSERT INTO vehicle_types (name) VALUES ('CAR'), ('TAXI'), ('UNKNOWN');