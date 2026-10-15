# Trajectory explorer

## Run the application

Start the API from the repository root:

```bash
venv/bin/python -m pip install -r requirements.txt
venv/bin/python -m uvicorn main:app --app-dir backend/src --reload
```

In `frontend/`:

```bash
npm install
npm run dev
```

Open the URL printed by Vite. `VITE_BACKEND_API_PATH` in the root `.env` can
specify an API URL, for example `http://localhost:8000/api/`. Without it, the
frontend uses `/api/`, proxied by Vite to port 8000. `VITE_PROXY_TARGET` can
override that development proxy target.

## Shared paths on the map

1. Load trajectories with the existing city/date/time filters, **or** use
   **Shared paths → Open a trajectory CSV → Open CSV on map**.
2. Set **SSPD threshold (meters)** and click **Cluster loaded trajectories**.
3. The existing Leaflet map switches to representative pathlets. Their width
   increases with distinct trajectory count; gray portions are unique.
4. Hover for counts or click a pathlet for contributing IDs, fractional original
   point intervals, timestamps, and CSV source rows when available.
5. Toggle **Overlay original trajectories** for comparison, or uncheck **Show
   shared paths** to restore the original routes. Selecting a trajectory in the
   bottom table filters its contributing pathlets without changing their counts.

To try the provided fixture, open
`backend/tests/data/trajectories/aalborg_germany.csv`. Start with **2000 meters**
to inspect its broad, kilometer-offset corridors. A 100 m threshold finds only
short shared portions. The threshold is a geometric distance, not a conversion
from a similarity percentage.

CSV preview and clustering work in memory through the API; they do not import
data into MySQL, write output/debug files, or use the standalone debug HTML.
The database is needed for city discovery, filtered database trajectories, and
dataset upload. Loading a new source or editing the threshold clears old
clustering results. The geometric algorithm's assumptions are documented in
[`backend/src/pathlets/README.md`](../backend/src/pathlets/README.md).

## Checks

```bash
npm run lint
npm run build
npm test
npm run test:types
npx playwright install chromium
npm run test:e2e
```

Vitest covers explorer interactions, API transport, and map-layer contents.
Playwright starts isolated frontend/API servers on ports 5175/8011 and exercises
the supplied CSV through the real API and Leaflet canvas, including layer
toggles. Only the database city-list request is stubbed. The browser test writes
a frontend screenshot into `test-results/`; it does not use pipeline debug views.
