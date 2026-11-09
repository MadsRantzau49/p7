import math

from models.similarity import GPSCoordinate, Pathlet, ProjectedPathlet, ProjectedPoint, ProjectedTrajectory
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

def inverse_projection(pathlets: list[ProjectedPathlet], transformer: Transformer,) -> list[Pathlet]:
    """Convert projected pathlet points back to GPS coordinates in degrees."""
    if not pathlets:
        return []

    gps_pathlets = []
    for pathlet in pathlets:
        gps_points = []
        for point in pathlet.points:
            longitude, latitude = transformer.transform(
                point.x, point.y, direction=TransformDirection.INVERSE
            )
            gps_points.append(GPSCoordinate(latitude=latitude, longitude=longitude))

        gps_pathlets.append(
            Pathlet(
                count=pathlet.count,
                points=gps_points,
                support=pathlet.support,
            )
        )

    return gps_pathlets
