import math
from bisect import bisect_left, bisect_right
from dataclasses import replace

from models.similarity import (
    GPSCoordinate,
    Pathlet,
    Polyline,
    ProjectedPathlet,
    ProjectedPoint,
    ProjectedTrajectory,
)
from models.subtrajectory import Subtrajectory
from pyproj import Transformer
from pyproj.enums import TransformDirection


def centre_longitude(points) -> float:
    """Return the circular mean longitude of the points, in degrees.
    Use unit-circle coordinates to handle longitudes across the antimeridian.
    """
    x = sum(math.cos(math.radians(point.longitude)) for point in points)
    y = sum(math.sin(math.radians(point.longitude)) for point in points)
    return math.degrees(math.atan2(y, x))


def projection(
    trajectories: list[Subtrajectory],
) -> tuple[list[ProjectedTrajectory], Transformer]:
    """Project GPS trajectories into a shared local coordinate system in metres."""
    if not trajectories:
        raise ValueError("Projection requires at least one trajectory.")

    # Collect all points so one projection can be used for every trajectory.
    points = []

    for trajectory in trajectories:
        if not trajectory.points:
            raise ValueError("Each trajectory must contain at least one point.")

        for point in trajectory.points:
            points.append(point)

    # Centre a custom Transverse Mercator projection on the input data.
    centre_lat = sum(point.latitude for point in points) / len(points)
    centre_lon = centre_longitude(points)

    transformer = Transformer.from_crs(
        "EPSG:4326",
        f"+proj=tmerc +lat_0={centre_lat} +lon_0={centre_lon} +k=1 +x_0=0 +y_0=0 +datum=WGS84 +units=m",
        always_xy=True,
    )

    projected_trajectories = []

    for trajectory in trajectories:
        # Transform a complete section
        xs, ys = transformer.transform(
            [point.longitude for point in trajectory.points],
            [point.latitude for point in trajectory.points],
        )
        projected_points = [ProjectedPoint(x=x, y=y) for x, y in zip(xs, ys, strict=True)]

        projected_trajectories.append(
            ProjectedTrajectory(
                trajectory_id=trajectory.trajectory_id,
                projected_points=projected_points,
            )
        )

    return projected_trajectories, transformer


def _interval_points(polyline: Polyline, start_m: float, end_m: float) -> list[ProjectedPoint]:
    """Clip the representative at exact projected metre offsets, including its interior vertices."""
    if not polyline.points:
        return []

    def point_at(distance: float) -> ProjectedPoint:
        distance = max(0.0, min(distance, polyline.total_length))
        index = min(bisect_right(polyline.cumulative_lengths, distance) - 1, len(polyline.points) - 1)
        start = polyline.points[index]
        if index == len(polyline.points) - 1:
            return start
        end = polyline.points[index + 1]
        fraction = (distance - polyline.cumulative_lengths[index]) / polyline.segment_lengths[index]
        return ProjectedPoint(start.x + fraction * (end.x - start.x), start.y + fraction * (end.y - start.y))

    first = point_at(start_m)
    if end_m <= start_m:
        return [first]
    left = bisect_right(polyline.cumulative_lengths, start_m)
    right = bisect_left(polyline.cumulative_lengths, end_m)
    return [first, *polyline.points[left:right], point_at(end_m)]


def inverse_projection(
    pathlets: list[ProjectedPathlet],
    transformer: Transformer,
) -> list[Pathlet]:
    """Convert pathlets and exact support interval geometries back to GPS degrees."""
    if not pathlets:
        return []

    gps_pathlets = []
    def to_gps(point: ProjectedPoint) -> GPSCoordinate:
        longitude, latitude = transformer.transform(point.x, point.y, direction=TransformDirection.INVERSE)
        return GPSCoordinate(latitude=latitude, longitude=longitude)

    for pathlet_id, pathlet in enumerate(pathlets, start=1):
        polyline = Polyline.from_points(pathlet.points)
        support = [
            replace(
                interval,
                support_interval_id=interval_id,
                points=[
                    to_gps(point) for point in _interval_points(polyline, interval.start_m, interval.end_m)
                ],
            )
            for interval_id, interval in enumerate(pathlet.support, start=1)
        ]

        gps_pathlets.append(
            Pathlet(
                count=pathlet.count,
                points=[to_gps(point) for point in pathlet.points],
                support=support,
                pathlet_id=pathlet_id,
                length_m=polyline.total_length,
            )
        )

    return gps_pathlets
