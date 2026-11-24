import math

from models.similarity import GPSCoordinate, ProjectedPoint, ProjectedRoute, ProjectedSubtrajectory, Route
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
    subtrajectories: list[Subtrajectory],
) -> tuple[list[ProjectedSubtrajectory], Transformer]:
    """Project GPS subtrajectories into a shared local coordinate system in metres."""
    if not subtrajectories:
        raise ValueError("Projection requires at least one subtrajectory.")

    # Collect all points so one projection can be used for every subtrajectory.
    points = []

    for subtrajectory in subtrajectories:
        if not subtrajectory.points:
            raise ValueError("Each subtrajectory must contain at least one point.")

        for point in subtrajectory.points:
            points.append(point)

    # Centre a custom Transverse Mercator projection on the input data.
    centre_lat = sum(point.latitude for point in points) / len(points)
    centre_lon = centre_longitude(points)

    transformer = Transformer.from_crs(
        "EPSG:4326",
        f"+proj=tmerc +lat_0={centre_lat} +lon_0={centre_lon} +k=1 +x_0=0 +y_0=0 +datum=WGS84 +units=m",
        always_xy=True,
    )

    projected_subtrajectories = []

    for subtrajectory in subtrajectories:
        # Transform a complete subtrajectory
        xs, ys = transformer.transform(
            [point.longitude for point in subtrajectory.points],
            [point.latitude for point in subtrajectory.points],
        )
        projected_points = [ProjectedPoint(x=x, y=y) for x, y in zip(xs, ys, strict=True)]

        projected_subtrajectories.append(
            ProjectedSubtrajectory(
                trajectory_id=subtrajectory.trajectory_id,
                projected_points=projected_points,
            )
        )

    return projected_subtrajectories, transformer


def inverse_projection(
    routes: list[ProjectedRoute],
    transformer: Transformer,
) -> list[Route]:
    """Convert projected route points back to GPS coordinates in degrees."""
    if not routes:
        return []

    gps_routes = []
    for route in routes:
        gps_points = []
        for point in route.points:
            longitude, latitude = transformer.transform(
                point.x, point.y, direction=TransformDirection.INVERSE
            )
            gps_points.append(GPSCoordinate(latitude=latitude, longitude=longitude))

        gps_routes.append(
            Route(
                count=route.count,
                points=gps_points,
            )
        )

    return gps_routes
