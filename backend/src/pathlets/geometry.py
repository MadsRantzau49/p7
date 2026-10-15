"""Projection and allocation-light Euclidean polyline geometry."""

from math import atan2, ceil, cos, degrees, floor, hypot, isfinite, radians, sin

from pyproj import CRS, Geod, Transformer

from .models import (
    XY,
    Assignment,
    GPSTrajectory,
    MetricTrajectory,
    Projection,
    Segment,
)


def convert_to_meters(
    trajectories: list[GPSTrajectory], max_radius_m: float = 1_000_000
) -> tuple[list[MetricTrajectory], Projection]:
    """Use local ellipsoidal AEQD, rejecting extents with excessive distortion.

    A 1000 km radius has approximately 0.42% worst transverse scale error;
    this is a local projected metric, not an assertion of geodesic equality.
    Circular longitude averaging also handles small antimeridian datasets.
    """
    points = [point for trajectory in trajectories for point in trajectory.points]
    if not points or any(len(trajectory.points) < 2 for trajectory in trajectories):
        raise ValueError("each trajectory must have at least two points")
    if len({trajectory.trajectory_id for trajectory in trajectories}) != len(trajectories):
        raise ValueError("trajectory IDs must be unique")
    if any(
        not isfinite(p.longitude)
        or not isfinite(p.latitude)
        or not -180 <= p.longitude <= 180
        or not -90 <= p.latitude <= 90
        for p in points
    ):
        raise ValueError("GPS coordinates must be finite valid longitude/latitude values")
    longitude = degrees(
        atan2(sum(sin(radians(p.longitude)) for p in points), sum(cos(radians(p.longitude)) for p in points))
    )
    latitude = sum(p.latitude for p in points) / len(points)
    geod = Geod(ellps="WGS84")
    radius = max(geod.inv(longitude, latitude, p.longitude, p.latitude)[2] for p in points)
    if radius > max_radius_m or max_radius_m > 1_000_000:
        raise ValueError(f"dataset radius {radius:.0f} m exceeds projection limit; partition the input")
    crs = CRS.from_proj4(f"+proj=aeqd +lat_0={latitude} +lon_0={longitude} +datum=WGS84 +units=m")
    transformer = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    metric = [
        MetricTrajectory(
            trajectory.trajectory_id,
            tuple(transformer.transform(p.longitude, p.latitude) for p in trajectory.points),
            tuple(p.point_timestamp for p in trajectory.points),
            trajectory.source_rows,
        )
        for trajectory in trajectories
    ]
    return metric, Projection(crs.to_wkt(), longitude, latitude, radius)


def generate_segments(trajectories: list[MetricTrajectory]) -> list[Segment]:
    """Keep every original segment, including stationary intervals and timestamps."""
    segments: list[Segment] = []
    for trajectory in trajectories:
        for index, (start, end) in enumerate(
            zip(trajectory.coordinates, trajectory.coordinates[1:], strict=False)
        ):
            segments.append(
                Segment(
                    len(segments),
                    trajectory.trajectory_id,
                    index,
                    start,
                    end,
                    (index, index + 1),
                    (trajectory.timestamps[index], trajectory.timestamps[index + 1]),
                )
            )
    return segments


def interpolate(start: XY, end: XY, fraction: float) -> XY:
    """Interpolate coordinates without constructing a geometry object."""
    return start[0] + fraction * (end[0] - start[0]), start[1] + fraction * (end[1] - start[1])


def project_fraction(point: XY, start: XY, end: XY) -> float:
    """Return the unclamped projection fraction on a line (zero for a point)."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    denominator = dx * dx + dy * dy
    return ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / denominator if denominator else 0


def point_segment_distance(point: XY, start: XY, end: XY) -> float:
    """Calculate exact Euclidean distance to a closed, possibly degenerate segment."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    px, py = point[0] - start[0], point[1] - start[1]
    dot = px * dx + py * dy
    squared = dx * dx + dy * dy
    if dot <= 0 or not squared:
        return hypot(px, py)
    if dot >= squared:
        return hypot(point[0] - end[0], point[1] - end[1])
    # Cross-product form avoids interpolation roundoff on collinear interiors.
    return abs(dx * py - dy * px) / hypot(dx, dy)


def sspd(first: tuple[XY, ...], second: tuple[XY, ...]) -> float:
    """Return symmetric mean vertex-to-polyline distance; equality is accepted.

    Vertices retain their original sampling weights, as required by SPD.
    Consecutive duplicates remain vertices; no Shapely objects are allocated.
    """
    if not first or not second:
        raise ValueError("SSPD requires two nonempty polylines")
    if first == second:
        return 0.0

    def directed(source: tuple[XY, ...], target: tuple[XY, ...]) -> float:
        edges = tuple(zip(target, target[1:], strict=False)) or ((target[0], target[0]),)
        return sum(min(point_segment_distance(p, a, b) for a, b in edges) for p in source) / len(source)

    return (directed(first, second) + directed(second, first)) / 2


def interval_coordinates(trajectory: MetricTrajectory, interval: Assignment) -> tuple[XY, ...]:
    """Extract an original interval, interpolating only its fractional endpoints."""
    coordinates = trajectory.coordinates

    def at(position: float) -> XY:
        index = min(floor(position), len(coordinates) - 2)
        return interpolate(coordinates[index], coordinates[index + 1], position - index)

    return (
        at(interval.start),
        *(coordinates[i] for i in range(floor(interval.start) + 1, ceil(interval.end))),
        at(interval.end),
    )


def length(coordinates: tuple[XY, ...]) -> float:
    """Return polyline length in projected meters."""
    return sum(hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(coordinates, coordinates[1:], strict=False))
