CREATE TABLE vehicle_types (
    vehicle_type_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(32) NOT NULL UNIQUE
);

INSERT INTO vehicle_types (name) VALUES ('CAR'), ('TAXI'), ('UNKNOWN');