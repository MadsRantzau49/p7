
## Start backend and frontend

```bash
docker compose -f docker/app.compose.yml up --build -d
```

## Start trajectory builder

```bash
docker compose -f docker/trajectory-builder.compose.yml up --build -d
```

## Stop everything

```bash
docker compose -f docker/app.compose.yml down
docker compose -f docker/trajectory-builder.compose.yml down
```

## Start the database (when on the server)

```bash
docker compose -f docker/database.compose.yml up -d
```

## Stop the database (when on the server)

```bash
docker compose -f docker/database.compose.yml down
```

URLs:

- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- API docs: http://localhost:8000/docs
- Trajectory builder: http://localhost:5174

`-d` runs the containers in the background and returns the terminal immediately.
