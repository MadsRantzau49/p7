ALTER TABLE uniformed_trajectories
    RENAME COLUMN taxi_id TO vehicle_id,
    ALGORITHM=INPLACE, LOCK=NONE;

ALTER TABLE uniformed_trajectories
    ADD COLUMN vehicle_type ENUM('CAR', 'UNKNOWN') NOT NULL DEFAULT 'CAR' AFTER city,
    ALGORITHM=INSTANT;