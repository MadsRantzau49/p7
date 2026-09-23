# Backend

- `src/main.py`: start the backend.
- `src/router.py`: define API routes only.
- `src/services/`: Core business logic of an application
- `src/lib/`: small reusable functions.
- `src/models/`: classes.
- `src/database/`: MySQL connection and queries.
- `tests/`: api, unit and integration tests.



## Uploading a dataset

`POST /api/datasets/upload` stores a CSV file as a new dataset.

The request is `multipart/form-data` with two fields:

| Field  | Description |
|--------|-------------|
| `name` | The dataset's name, 1–50 characters. Also used as the trajectories' city, so it must not match an existing dataset or city. |
| `file` | A UTF-8 CSV file, at most 50 MB. |

Example with curl, while the backend runs on port 8000:

```bash
curl -X POST http://localhost:8000/api/datasets/upload \
  -F "name=Copenhagen" \
  -F "file=@copenhagen.csv"
```

You can also try it in the browser at http://localhost:8000/docs.

### File format

The first line must be exactly this header:

```csv
trajectory_id,vehicle_id,vehicle_type,timestamp,longitude,latitude
t1,7,CAR,2024-01-31 14:05:00,12.5683,55.6761
t1,7,CAR,2024-01-31 14:05:30,12.5701,55.6770
t2,8,TAXI,2024-01-31T09:00:00,12.4500,55.6100
t2,8,TAXI,2024-01-31T09:00:15,12.4512,55.6108
```

Each row is one GPS point. All rows with the same `trajectory_id` form one trajectory.

| Column | Rule |
|--------|------|
| `trajectory_id` | Any text, 1–255 characters. |
| `vehicle_id` | Whole number from 0 to 2147483647. |
| `vehicle_type` | `CAR`, `TAXI` or `UNKNOWN`. |
| `timestamp` | `YYYY-MM-DD HH:MM:SS` or `YYYY-MM-DDTHH:MM:SS`, local time where the point was recorded. No time zone. |
| `longitude` | −180 to 180. |
| `latitude` | −90 to 90. |

Each trajectory must:
- have at least 2 points
- use the same `vehicle_id` and `vehicle_type` on every point
- not have two points with the same timestamp

Points can be in any order in the file. They are sorted by timestamp before they are stored. Blank lines are skipped.

The upload does not check whether movement is realistic, e.g. a vehicle moving 2,000 km/h. Faulty points are cleaned later in the pipeline.

### Responses

| Status | Meaning | Body |
|--------|---------|------|
| 201 | Stored | `{"dataset_id": 3, "name": "Copenhagen"}` |
| 409 | The name is already used by a dataset or city | `{"detail": "a dataset or city named 'Copenhagen' already exists"}` |
| 413 | The file is larger than 50 MB | `{"detail": "file is larger than 50 MB"}` |
| 422 | The file breaks a rule | `{"detail": [{"line": 4, "message": "latitude: Input should be less than or equal to 90"}]}` |

If anything is wrong, nothing is stored. A 422 lists up to 100 problems with their line numbers. Line 1 is the header.
