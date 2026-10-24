CREATE TABLE datasets (
    dataset_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    city_id INT NOT NULL,

    FOREIGN KEY (city_id) REFERENCES cities (city_id)
);