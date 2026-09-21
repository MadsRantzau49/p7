const map = L.map("map").setView([57.035, 9.908], 14);

L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution:
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
}).addTo(map);

const points = [];

const route = L.polyline([], {
  color: "#ba4f2d",
  weight: 4,
}).addTo(map);

const markers = L.layerGroup().addTo(map);

const pointList = document.querySelector("#point-list");
const pointCount = document.querySelector("#point-count");

const undoButton = document.querySelector("#undo-button");
const clearButton = document.querySelector("#clear-button");
const exportButton = document.querySelector("#export-button");

const startInput = document.querySelector("#start-timestamp");
const status = document.querySelector("#status");

const trajectoryNameInput =
  document.querySelector("#trajectory-name");

const intervalInput =
  document.querySelector("#point-interval");

/*
 * Set default timestamp to current local time.
 */
const now = new Date();

now.setSeconds(0, 0);

startInput.value = new Date(
  now.getTime() - now.getTimezoneOffset() * 60000,
)
  .toISOString()
  .slice(0, 19);

/*
 * Add point when map is clicked.
 */
map.on("click", ({ latlng }) => {
  points.push({
    latitude: Number(latlng.lat.toFixed(6)),
    longitude: Number(latlng.lng.toFixed(6)),
  });

  render();
});

/*
 * Remove most recent point.
 */
undoButton.addEventListener("click", () => {
  points.pop();
  render();
});

/*
 * Clear all points.
 */
clearButton.addEventListener("click", () => {
  points.length = 0;
  render();
});

/*
 * Export trajectory as JSON.
 */
exportButton.addEventListener("click", async () => {
  if (
    !trajectoryNameInput.reportValidity() ||
    !startInput.reportValidity() ||
    !intervalInput.reportValidity()
  ) {
    return;
  }

  if (points.length === 0) {
    return;
  }

  const localTimestamp = new Date(startInput.value);

  const fixture = {
    schema_version: 1,

    name:
      trajectoryNameInput.value.trim(),

    start_timestamp:
      localTimestamp.toISOString(),

    interval_seconds:
      Number(intervalInput.value),

    points: points,
  };

  const json = JSON.stringify(
    fixture,
    null,
    2,
  );

  try {
    const response = await fetch("/fixtures", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: json,
    });
    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.error);
    }

    status.textContent =
      `Saved to ${result.path}.`;
  } catch (error) {
    status.textContent =
      `Could not save fixture: ${error.message}`;
  }
});

/*
 * Update map + UI.
 */
function render() {
  const latLngs = points.map(
    (point) => [
      point.latitude,
      point.longitude,
    ],
  );

  route.setLatLngs(latLngs);

  markers.clearLayers();

  points.forEach(
    (point, index) => {
      L.circleMarker(
        [
          point.latitude,
          point.longitude,
        ],
        {
          radius: 6,
          weight: 2,
        },
      )
        .bindTooltip(
          String(index + 1),
          {
            permanent: false,
            direction: "top",
          },
        )
        .addTo(markers);
    },
  );

  if (points.length > 0) {
    pointList.innerHTML =
      points
        .map(
          (point, index) =>
            `<li>
              ${index + 1}.
              ${point.latitude.toFixed(6)},
              ${point.longitude.toFixed(6)}
            </li>`,
        )
        .join("");
  } else {
    pointList.innerHTML =
      "<li>No points yet.</li>";
  }

  pointCount.textContent =
    points.length;

  const empty =
    points.length === 0;

  undoButton.disabled = empty;
  clearButton.disabled = empty;
  exportButton.disabled = empty;

  status.textContent = "";
}

/*
 * Important:
 * Leaflet needs to know when its container changes size.
 */
const mapElement =
  document.querySelector("#map");

const resizeObserver =
  new ResizeObserver(() => {
    map.invalidateSize();
  });

resizeObserver.observe(mapElement);

/*
 * Also recalculate once after page load.
 */
window.addEventListener(
  "load",
  () => {
    setTimeout(() => {
      map.invalidateSize();
    }, 100);
  },
);
