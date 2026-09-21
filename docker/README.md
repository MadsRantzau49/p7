# Run the app

Start everything:

```bash
docker compose -f docker/compose.yml up --build -d
```

Start only the trajectory builder:

```bash
docker compose -f docker/compose.yml up --build -d trajectory-builder
```

Start only the API and its database:

```bash
docker compose -f docker/compose.yml up --build -d api
```

Open <http://localhost:5173> for the trajectory builder or <http://localhost:8000/docs> for the API.

Stop everything:

```bash
docker compose -f docker/compose.yml down
```
