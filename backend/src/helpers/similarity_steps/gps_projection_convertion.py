from models.similarity import (
    GPSCoordinate,
    Pathlet,
    ProjectedTrajectory,
    Projection,
    ProjectedPathlet
)

from pyproj import Transformer
from pyproj.enums import TransformDirection

from models.subtrajectory import Subtrajectory
from models.similarity import Pathlet

class GpsProjectionConverter:
    def __init__(self) -> None:
        self._projection_transformer: Transformer | None = None

    def projection(
        self,
        trajectories: list[Subtrajectory],
    ) -> list[ProjectedTrajectory]:

        if not trajectories:
            raise ValueError("Projection requires at least one trajectory.")

        # Collect all points so one projection can be used for every trajectory.
        points = []

        for trajectory in trajectories:
            if not trajectory.points:
                raise ValueError("Each trajectory must contain at least one point.")

            for point in trajectory.points:
                points.append(point)

        # Choose a UTM zone based on the centre of the input data.
        # This is suitable when the trajectories cover a local or regional area.
        centre_latitude = sum(point.latitude for point in points) / len(points)
        centre_longitude = sum(point.longitude for point in points) / len(points)

        utm_zone = int((centre_longitude + 180) / 6) + 1
        epsg_code = (32600 if centre_latitude >= 0 else 32700) + utm_zone

        transformer = Transformer.from_crs(
            "EPSG:4326",
            f"EPSG:{epsg_code}",
            always_xy=True,
        )
        self._projection_transformer = transformer

        projected_trajectories = []

        for trajectory in trajectories:
            projected_points = []

            for point in trajectory.points:
                # always_xy=True means the inputs must be longitude, then latitude.
                x, y = transformer.transform(
                    point.longitude,
                    point.latitude,
                )

                projected_points.append(Projection(x=x, y=y))

            projected_trajectories.append(
                ProjectedTrajectory(
                    trajectory_id=trajectory.trajectory_id,
                    projected_points=projected_points,
                )
            )

        return projected_trajectories

    def inverse_projection(self, pathlets: list[ProjectedPathlet]) -> list[Pathlet]:
        """Convert every representative point back using the most recent Step 1 projection."""
        if not pathlets:
            return []
        if self._projection_transformer is None:
            raise ValueError("Run projection() before inverse_projection() on the same service.")

        gps_pathlets = []
        for pathlet in pathlets:
            gps_points = []
            for point in pathlet.representative.points:
                # always_xy=True also means the inverse returns longitude, then latitude.
                longitude, latitude = self._projection_transformer.transform(
                    point.x, point.y, direction=TransformDirection.INVERSE
                )
                gps_points.append(GPSCoordinate(latitude=latitude, longitude=longitude))

            gps_pathlets.append(
                Pathlet(
                    count=pathlet.count,
                    points=gps_points,
                )
            )

        return gps_pathlets