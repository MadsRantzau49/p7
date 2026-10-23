
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

## The database server (UCloud)

The shared database runs only on the UCloud VM `p7`.

- PostgreSQL 18 + PostGIS 3.6 + MobilityDB 1.3, database `p7`, user `postgres`
- Data: `/work/P7/pgdata`
- Password: `POSTGRES_PASSWORD` in `/work/P7/p7/.env` on the VM
- The database listens on the VM's own `127.0.0.1:5432`. Connect through SSH (below)

## Connect to the database

DataGrip, with its built-in SSH tunnel:

- General tab: host `localhost`, port `5432`, database `p7`, user `postgres`, the password from the VM
- SSH/SSL tab: tick "Use SSH tunnel". Host `ssh.cloud.sdu.dk`, the job's SSH port, user `ucloud`,
  authentication "Key pair" with your private key

With the tunnel ticked, DataGrip reads the host and port from the VM's side, so the port is 5432.

URLs:

- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- API docs: http://localhost:8000/docs
- Trajectory builder: http://localhost:5174

`-d` runs the containers in the background and returns the terminal immediately.
