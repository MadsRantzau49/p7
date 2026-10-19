
## Start backend and frontend

```bash
docker compose -f docker/app.compose.yml up --build -d
```

## Start trajectory builder

```bash
LOCAL_UID="$(id -u)" LOCAL_GID="$(id -g)" docker compose -f docker/trajectory-builder.compose.yml up --build -d
```

The builder runs as your user and saves CSV fixtures with your ownership. This
allows Snap-packaged Firefox to read them for uploads. The container listens on
port 8080; the builder is still available at http://localhost:5174.

For older, root-owned exports, run this once from the repository root:

```bash
sudo chown -R "$(id -u):$(id -g)" backend/tests/data/trajectories
```

## Stop everything

```bash
docker compose -f docker/app.compose.yml down
docker compose -f docker/trajectory-builder.compose.yml down
```

URLs:

- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- API docs: http://localhost:8000/docs
- Trajectory builder: http://localhost:5174

`-d` runs the containers in the background and returns the terminal immediately.
