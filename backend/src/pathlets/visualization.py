"""Optional static diagnostics and Leaflet HTML, renderable from saved snapshots."""

import argparse
import html
import json
from pathlib import Path
from typing import Any

from pyproj import Transformer


def _sample(items: list[Any], size: int) -> list[Any]:
    if len(items) <= size:
        return items
    return [items[index * len(items) // size] for index in range(size)]


def _interval(trajectories: dict[str, Any], assignment: dict[str, Any]) -> list[list[float]]:
    from .geometry import interval_coordinates
    from .models import Assignment, MetricTrajectory

    trajectory = trajectories[assignment["trajectory_id"]]
    coordinates = tuple(tuple(point) for point in trajectory["coordinates"])
    metric = MetricTrajectory(trajectory["trajectory_id"], coordinates, (None,) * len(coordinates))
    return [list(point) for point in interval_coordinates(metric, Assignment(**assignment))]


def _leaflet(snapshot: dict[str, Any], output: Path) -> None:
    inverse = Transformer.from_crs(snapshot["projection"]["crs"], "EPSG:4326", always_xy=True)
    originals = [
        [[lat, lon] for lon, lat in (inverse.transform(*point) for point in trajectory["coordinates"])]
        for trajectory in snapshot["trajectories"]
    ]
    # Escape '<' so source IDs cannot terminate a script element.
    pathlets = json.dumps(snapshot["data"]).replace("<", "\\u003c")
    output.write_text(
        """<!doctype html><html><head><meta charset="utf-8">
<title>SSPD pathlets</title><link rel="stylesheet"
href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>body{margin:0}#map{height:100vh}.key{background:white;padding:10px}</style>
</head><body><div id="map"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script><script>
const map=L.map('map');
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{
attribution:'© OpenStreetMap contributors'}).addTo(map);
const originals="""
        + json.dumps(originals)
        + ";const pathlets="
        + pathlets
        + """;
originals.forEach(p=>L.polyline(p,{color:'#666',weight:1,opacity:0.25}).addTo(map));
const colors=['#999','#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd'];
pathlets.forEach(p=>{
 const line=L.polyline(p.coordinates,{color:colors[Math.min(p.count-1,5)],
 weight:2+2*Math.sqrt(p.count),opacity:0.85}).addTo(map);
 const text=document.createElement('pre');
 text.textContent=p.pathlet_id+' — count '+p.count+'\\n'+JSON.stringify(p.assignments,null,2);
 line.bindPopup(text);
});
map.fitBounds(L.latLngBounds(originals.flat()));
const key=L.control({position:'topright'});key.onAdd=()=>{
const d=L.DomUtil.create('div','key');
d.textContent='SSPD pathlets · width = distinct trajectories';return d;};
key.addTo(map);
</script></body></html>""",
        encoding="utf-8",
    )


def render_snapshot(snapshot_path: Path, output: Path | None = None, sample_size: int = 120) -> Path:
    """Render one saved stage, sampling drawings only; numerical data stays intact."""
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    step = snapshot["step"]
    output = output or snapshot_path.with_suffix(".html" if step == 9 else ".png")
    if step == 9:
        _leaflet(snapshot, output)
        return output

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    figure, axes = plt.subplots(figsize=(11, 9))
    trajectories = {trajectory["trajectory_id"]: trajectory for trajectory in snapshot["trajectories"]}
    palette = "tab10" if len(trajectories) <= 10 else "tab20"
    colors = {
        trajectory_id: plt.get_cmap(palette)(index % (10 if palette == "tab10" else 20))
        for index, trajectory_id in enumerate(sorted(trajectories))
    }

    def draw(coordinates, **kwargs):
        if coordinates:
            axes.plot([p[0] for p in coordinates], [p[1] for p in coordinates], **kwargs)

    for trajectory_id, trajectory in trajectories.items():
        draw(
            trajectory["coordinates"],
            color=colors[trajectory_id],
            linewidth=0.7,
            alpha=0.35,
            label=trajectory_id if len(trajectories) <= 12 else None,
        )
    segments = {segment["segment_id"]: segment for segment in snapshot["segments"]}
    data = snapshot["data"]
    if step == 1:
        for trajectory_id, trajectory in trajectories.items():
            points = _sample(trajectory["coordinates"], sample_size)
            axes.scatter([p[0] for p in points], [p[1] for p in points], s=8, color=colors[trajectory_id])
    elif step in (2, 3):
        for segment in _sample(list(segments.values()), sample_size):
            draw(
                [segment["start"], segment["end"]],
                color=colors[segment["trajectory_id"]],
                linewidth=1,
                marker=".",
                markersize=3,
            )
            if step == 3:
                x0, y0 = (min(segment["start"][i], segment["end"][i]) for i in (0, 1))
                x1, y1 = (max(segment["start"][i], segment["end"][i]) for i in (0, 1))
                axes.add_patch(
                    Rectangle(
                        (x0, y0),
                        x1 - x0,
                        y1 - y0,
                        fill=False,
                        edgecolor=colors[segment["trajectory_id"]],
                        alpha=0.45,
                    )
                )
    elif step in (4, 5):
        for pair in _sample(data, sample_size):
            first_id, second_id = pair if step == 4 else (pair["first_id"], pair["second_id"])
            first, second = segments[first_id], segments[second_id]
            for segment in (first, second):
                draw([segment["start"], segment["end"]], color=colors[segment["trajectory_id"]], linewidth=2)
            centers = [[(s["start"][i] + s["end"][i]) / 2 for i in (0, 1)] for s in (first, second)]
            draw(centers, color="gray" if step == 4 else "green", linewidth=0.7, linestyle="--", alpha=0.6)
    elif step == 6:
        shared = [cluster for cluster in data if len(cluster["trajectory_ids"]) > 1]
        for cluster in _sample(shared, min(sample_size, 12)):
            representative = segments[cluster["representative_id"]]
            for member_id in cluster["member_ids"]:
                member = segments[member_id]
                draw([member["start"], member["end"]], color="orange", linewidth=2, alpha=0.5)
            draw([representative["start"], representative["end"]], color="black", linewidth=2.5)
            axes.annotate(str(len(cluster["trajectory_ids"])), representative["start"], fontsize=8)
    else:
        sampled = _sample(data, sample_size)
        label_indices = set(_sample(list(range(len(sampled))), 16))
        for index, candidate in enumerate(sampled):
            representative = candidate["representative"]
            count = len(candidate["assignments"])
            coordinates = candidate.get("coordinates") or _interval(trajectories, representative)
            draw(
                coordinates,
                color=colors[representative["trajectory_id"]],
                linewidth=1 + 1.4 * count**0.5,
                alpha=0.85,
            )
            if count > 1 and index in label_indices:
                midpoint = coordinates[len(coordinates) // 2]
                axes.annotate(str(count), (midpoint[0], midpoint[1]), fontsize=7)
    axes.set_aspect("equal", adjustable="datalim")
    axes.set_xlabel("Local projected easting (m)")
    axes.set_ylabel("Local projected northing (m)")
    axes.set_title(
        f"{step:02d} {snapshot['name'].replace('_', ' ')}\n"
        f"Diagnostic sample ≤ {sample_size}; complete results in adjacent JSON"
    )
    if len(trajectories) <= 12:
        axes.legend(loc="best", fontsize=7)
    axes.grid(alpha=0.15)
    figure.tight_layout()
    figure.savefig(output, dpi=150)
    plt.close(figure)
    return output


def main() -> None:
    """Regenerate one diagnostic independently of the clustering algorithm."""
    parser = argparse.ArgumentParser(description=html.unescape(__doc__ or ""))
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--sample-size", type=int, default=120)
    args = parser.parse_args()
    render_snapshot(args.snapshot, args.output, args.sample_size)


if __name__ == "__main__":
    main()
