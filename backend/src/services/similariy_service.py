from models.subpath import Subpath
from models.similarity import Coordinate, ProjectedTrajectory, Pathlet, TrajectorySegments

from pyproj import Transformer


class SimilarityService:

    def projection(
        self,
        trajectories: list[Subpath],
    ) -> list[ProjectedTrajectory]:

        # Collect all points so one projection can be used for every trajectory.
        points = []

        for trajectory in trajectories:
            for point in trajectory.points:
                points.append(point)

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

        projected_trajectories = []

        for trajectory in trajectories:
            projected_points = []

            for point in trajectory.points:
                # always_xy=True means the inputs must be longitude, then latitude.
                x, y = transformer.transform(
                    point.longitude,
                    point.latitude,
                )

                projected_points.append(Coordinate(x=x, y=y))

            projected_trajectories.append(
                ProjectedTrajectory(
                    trajectory_id=trajectory.trajectory_id,
                    projected_points=projected_points,
                )
            )

        return projected_trajectories

    def generate_segments(
        self,
        trajectories: list[ProjectedTrajectory],
    ) -> list[TrajectorySegments]:
        """Split each trajectory into segments between consecutive points (Step 2).
        (a, b, c, d) -> (a, b), (b, c), (c, d). Each segment keeps its
        trajectory ID and 0-based index j (connecting point j to j + 1).
        """

        segments = []

        for trajectory in trajectories:
            points = trajectory.projected_points
            # One segment per pair of consecutive points: (a,b,c,d) -> (a,b),(b,c),(c,d)
            for j in range(len(points) - 1):
                segments.append(
                    TrajectorySegments(
                        trajectory_id=trajectory.trajectory_id,
                        segment_index=j,
                        start=points[j],
                        end=points[j + 1],
                    )
                )

        return segments

    def FDS(
            self, 
            subpaths: list[Subpath]
        ) -> list[Pathlet]:
        # Step 1: Projection
        projected_trajectories = self.projection(subpaths)

        #Step 2: Generate Segments
        segments = self.generate_segments(projected_trajectories)

        #Step 3: Build R-tree


        #Step 4: Find Matching Segment Pairs


        #Step 5: Construct Candidate Clusters


        #Step 6: Extend Candidate Clusters


        #Step 7: Select Final Pathlets


        #Step 8: Inverse Projection
        
