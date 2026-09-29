const map = L.map("map").setView([57.035, 9.908], 14);

L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution:
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
}).addTo(map);

const routeLine = L.polyline([], {
  color: "#ba4f2d",
  weight: 4,
}).addTo(map);
const markers = L.layerGroup().addTo(map);

const routeList = document.querySelector("#route-list");
const routeCount = document.querySelector("#route-count");
const pointList = document.querySelector("#point-list");
const pointCount = document.querySelector("#point-count");
const newRouteButton = document.querySelector("#new-route-button");
const deleteRouteButton = document.querySelector("#delete-route-button");
const undoButton = document.querySelector("#undo-button");
const clearButton = document.querySelector("#clear-button");
const exportButton = document.querySelector("#export-button");
const trajectoryNameInput = document.querySelector("#trajectory-name");
const trajectoryIdInput = document.querySelector("#trajectory-id");
const cityInput = document.querySelector("#city");
const sourceIdInput = document.querySelector("#source-id");
const vehicleIdInput = document.querySelector("#vehicle-id");
const vehicleTypeInput = document.querySelector("#vehicle-type");
const startInput = document.querySelector("#start-timestamp");
const intervalInput = document.querySelector("#point-interval");
const status = document.querySelector("#status");

const routeInputs = [
  trajectoryNameInput,
  trajectoryIdInput,
  cityInput,
  sourceIdInput,
  vehicleIdInput,
  vehicleTypeInput,
  startInput,
  intervalInput,
];
const routes = [];
let activeRouteIndex = 0;

const now = new Date();
now.setSeconds(0, 0);
startInput.value = new Date(
  now.getTime() - now.getTimezoneOffset() * 60000,
)
  .toISOString()
  .slice(0, 19);

routes.push(readRouteInputs([]));
render();

map.on("click", ({ latlng }) => {
  activeRoute().points.push({
    latitude: Number(latlng.lat.toFixed(6)),
    longitude: Number(latlng.lng.toFixed(6)),
  });
  status.textContent = "";
  render();
});

routeInputs.forEach((input) => {
  input.addEventListener("input", () => {
    saveActiveRoute();
    status.textContent = "";
    renderRouteList();
    updateButtons();
  });
});

newRouteButton.addEventListener("click", () => {
  saveActiveRoute();

  const error = routeValidationError(activeRoute());
  if (error) {
    status.textContent = error;
    return;
  }

  if (activeRoute().points.length < 2) {
    status.textContent = "Add at least two points before starting a new route.";
    return;
  }

  const current = activeRoute();
  routes.push({
    trajectoryName: nextRouteName(),
    databaseTrajectoryId: "",
    city: current.city,
    sourceId: "",
    vehicleId: current.vehicleId,
    vehicleType: current.vehicleType,
    startTimestamp: current.startTimestamp,
    intervalSeconds: current.intervalSeconds,
    points: [],
  });
  activeRouteIndex = routes.length - 1;
  loadActiveRoute();
  status.textContent = `Started route ${activeRouteIndex + 1}.`;
});

deleteRouteButton.addEventListener("click", () => {
  if (routes.length === 1) {
    return;
  }

  routes.splice(activeRouteIndex, 1);
  activeRouteIndex = Math.min(activeRouteIndex, routes.length - 1);
  loadActiveRoute();
  status.textContent = "Route deleted.";
});

undoButton.addEventListener("click", () => {
  activeRoute().points.pop();
  status.textContent = "";
  render();
});

clearButton.addEventListener("click", () => {
  activeRoute().points.length = 0;
  status.textContent = "";
  render();
});

exportButton.addEventListener("click", async () => {
  saveActiveRoute();

  for (let index = 0; index < routes.length; index += 1) {
    const error = routeValidationError(routes[index]);
    if (error || routes[index].points.length < 2) {
      activeRouteIndex = index;
      loadActiveRoute();
      status.textContent = error || `Route ${index + 1} needs at least two points.`;
      return;
    }
  }

  const trajectoryNames = routes.map((item) => item.trajectoryName);
  if (new Set(trajectoryNames).size !== trajectoryNames.length) {
    status.textContent = "Every route needs a unique CSV trajectory ID.";
    return;
  }

  const rows = routes.flatMap((item) => {
    const startTime = new Date(item.startTimestamp);
    const intervalMilliseconds = Number(item.intervalSeconds) * 1000;

    return item.points.map((point, index) => [
      item.trajectoryName,
      item.vehicleId,
      item.vehicleType,
      formatTimestamp(new Date(startTime.getTime() + index * intervalMilliseconds)),
      point.longitude,
      point.latitude,
      item.city,
      item.sourceId,
      item.databaseTrajectoryId,
    ]);
  });
  const csv = [
    "trajectory_id,vehicle_id,vehicle_type,timestamp,longitude,latitude,city,source_id,database_trajectory_id",
    ...rows.map((row) => row.map(escapeCsvValue).join(",")),
  ].join("\n") + "\n";

  try {
    const response = await fetch("/fixtures", {
      method: "POST",
      headers: {
        "Content-Type": "text/csv; charset=utf-8",
      },
      body: csv,
    });
    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.error);
    }

    status.textContent = `Saved ${routes.length} routes to ${result.path}.`;
  } catch (error) {
    status.textContent = `Could not save fixture: ${error.message}`;
  }
});

function activeRoute() {
  return routes[activeRouteIndex];
}

function readRouteInputs(points) {
  return {
    trajectoryName: trajectoryNameInput.value.trim(),
    databaseTrajectoryId: trajectoryIdInput.value,
    city: cityInput.value.trim(),
    sourceId: sourceIdInput.value.trim(),
    vehicleId: vehicleIdInput.value,
    vehicleType: vehicleTypeInput.value,
    startTimestamp: startInput.value,
    intervalSeconds: intervalInput.value,
    points,
  };
}

function saveActiveRoute() {
  routes[activeRouteIndex] = readRouteInputs(activeRoute().points);
}

function loadActiveRoute() {
  const item = activeRoute();
  trajectoryNameInput.value = item.trajectoryName;
  trajectoryIdInput.value = item.databaseTrajectoryId;
  cityInput.value = item.city;
  sourceIdInput.value = item.sourceId;
  vehicleIdInput.value = item.vehicleId;
  vehicleTypeInput.value = item.vehicleType;
  startInput.value = item.startTimestamp;
  intervalInput.value = item.intervalSeconds;
  render();
}

function routeValidationError(item) {
  if (!/^[a-z0-9_-]{1,255}$/.test(item.trajectoryName)) {
    return "CSV trajectory IDs must use lowercase letters, numbers, underscores, or hyphens.";
  }

  const vehicleId = Number(item.vehicleId);
  if (!/^\d+$/.test(item.vehicleId) || vehicleId > 2147483647) {
    return "Vehicle ID must be a whole number from 0 to 2147483647.";
  }

  if (!["UNKNOWN", "CAR", "TAXI"].includes(item.vehicleType)) {
    return "Choose a vehicle type.";
  }

  if (!item.startTimestamp || Number.isNaN(new Date(item.startTimestamp).getTime())) {
    return "Choose a valid trajectory start time.";
  }

  if (!(Number(item.intervalSeconds) > 0)) {
    return "Point interval must be greater than zero.";
  }

  if (
    item.databaseTrajectoryId !== "" &&
    !/^\d+$/.test(item.databaseTrajectoryId)
  ) {
    return "Trajectory ID must be a non-negative whole number or empty.";
  }

  return "";
}

function nextRouteName() {
  let number = routes.length + 1;
  let name;

  do {
    const suffix = `_${number}`;
    name = `${routes[0].trajectoryName.slice(0, 255 - suffix.length)}${suffix}`;
    number += 1;
  } while (routes.some((item) => item.trajectoryName === name));

  return name;
}

function escapeCsvValue(value) {
  const text = String(value);

  if (/[",\r\n]/.test(text)) {
    return `"${text.replaceAll('"', '""')}"`;
  }

  return text;
}

function formatTimestamp(date) {
  const pad = (value, length = 2) => String(value).padStart(length, "0");
  const datePart = [
    date.getFullYear(),
    pad(date.getMonth() + 1),
    pad(date.getDate()),
  ].join("-");
  const timePart = [
    pad(date.getHours()),
    pad(date.getMinutes()),
    pad(date.getSeconds()),
  ].join(":");
  const milliseconds = date.getMilliseconds();

  return `${datePart} ${timePart}${milliseconds ? `.${pad(milliseconds, 3)}` : ""}`;
}

function render() {
  const points = activeRoute().points;
  const latLngs = points.map((point) => [point.latitude, point.longitude]);

  routeLine.setLatLngs(latLngs);
  markers.clearLayers();

  points.forEach((point, index) => {
    L.circleMarker([point.latitude, point.longitude], {
      radius: 6,
      weight: 2,
    })
      .bindTooltip(String(index + 1), {
        permanent: false,
        direction: "top",
      })
      .addTo(markers);
  });

  if (points.length > 0) {
    pointList.innerHTML = points
      .map(
        (point, index) =>
          `<li>${index + 1}. ${point.latitude.toFixed(6)}, ${point.longitude.toFixed(6)}</li>`,
      )
      .join("");
  } else {
    pointList.innerHTML = "<li>No points yet.</li>";
  }

  pointCount.textContent = points.length;
  renderRouteList();
  updateButtons();
}

function renderRouteList() {
  routeList.replaceChildren();
  routeCount.textContent = `${routes.length} ${routes.length === 1 ? "route" : "routes"}`;

  routes.forEach((item, index) => {
    const listItem = document.createElement("li");
    const button = document.createElement("button");
    const name = document.createElement("span");
    const count = document.createElement("span");

    button.type = "button";
    button.classList.toggle("active", index === activeRouteIndex);
    name.textContent = item.trajectoryName || `Route ${index + 1}`;
    count.textContent = `${item.points.length} pts`;
    button.append(name, count);
    button.addEventListener("click", () => {
      saveActiveRoute();
      activeRouteIndex = index;
      loadActiveRoute();
      status.textContent = "";
    });
    listItem.append(button);
    routeList.append(listItem);
  });
}

function updateButtons() {
  const noPoints = activeRoute().points.length === 0;
  undoButton.disabled = noPoints;
  clearButton.disabled = noPoints;
  newRouteButton.disabled = activeRoute().points.length < 2;
  deleteRouteButton.disabled = routes.length === 1;
  exportButton.disabled = routes.some((item) => item.points.length < 2);
}

const mapElement = document.querySelector("#map");
const resizeObserver = new ResizeObserver(() => {
  map.invalidateSize();
});
resizeObserver.observe(mapElement);

window.addEventListener("load", () => {
  setTimeout(() => {
    map.invalidateSize();
  }, 100);
});
