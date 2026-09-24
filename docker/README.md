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

Stop everything:

```bash
docker compose -f docker/compose.yml down
```
