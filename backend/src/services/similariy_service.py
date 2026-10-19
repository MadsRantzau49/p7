from models.subpath import Subpath
from models.similarity import Coordinate, TrajectoryInMeters, Pathlet

from pyproj import Transformer


class SimilarityService:

    def convert_gps_to_meter_coordinates(
        self,
        trajectories: list[Subpath],
    ) -> list[TrajectoryInMeters]:

        # Collect all points so one projection can be used for every trajectory.
        points = [
            point
            for trajectory in trajectories
            for point in trajectory.points
        ]

        if not points:
            return []

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

        converted_trajectories = []

        for trajectory in trajectories:
            meter_points = []

            for point in trajectory.points:
                # always_xy=True means the inputs must be longitude, then latitude.
                x, y = transformer.transform(
                    point.longitude,
                    point.latitude,
                )

                meter_points.append(Coordinate(x=x, y=y))

            converted_trajectories.append(
                TrajectoryInMeters(
                    trajectory_id=trajectory.trajectory_id,
                    meter_points=meter_points,
                )
            )

        return converted_trajectories


    def FDS(
            self, 
            subpaths: list[Subpath]
        ) -> list[Pathlet]:
        # Step 1: Convert GPS to Meters
        trajectories_in_meters = self.convert_gps_to_meter_coordinates(subpaths)

        #Step 2: Generate Segments


        #Step 3: Build R-tree


        #Step 4: Find Matching Segment Pairs


        #Step 5: Construct Candidate Clusters


        #Step 6: Extend Candidate Clusters


        #Step 7: Select Final Pathlets


        #Step 8: Convert Pathlets Back to GPS
        
