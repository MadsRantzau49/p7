from models.subpath import Subpath
from models.similarity import TrajectoryInMeters, Pathlet, TrajectorySegments


class SimilarityService:

    def convert_gps_to_meter_coordinates(
        self, 
        trajectories: list[Subpath],
    ) -> list[TrajectoryInMeters]:

        converted_trajectories = []

        for trajectory in trajectories:
            meter_trajectory = TrajectoryInMeters(
                trajectory_id=trajectory.trajectory_id,
                meter_points=[],
            )

            # TODO: convert each GPS point and append Coordinate(x, y)

            converted_trajectories.append(meter_trajectory)

        return converted_trajectories

    def generate_segments(
        self,
        trajectories: list[TrajectoryInMeters],
    ) -> list[TrajectorySegments]:
        """Split each trajectory into segments between consecutive points (Step 2).
        (a, b, c, d) -> (a, b), (b, c), (c, d). Each segment keeps its
        trajectory ID and 0-based index j (connecting point j to j + 1).
        """

        segments = []

        for trajectory in trajectories:
            points = trajectory.meter_points
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
        # Step 1: Convert GPS to Meters
        trajectories_in_meters = self.convert_gps_to_meter_coordinates(subpaths)

        #Step 2: Generate Segments
        segments = self.generate_segments(trajectories_in_meters)

        #Step 3: Build R-tree


        #Step 4: Find Matching Segment Pairs


        #Step 5: Construct Candidate Clusters


        #Step 6: Extend Candidate Clusters


        #Step 7: Select Final Pathlets


        #Step 8: Convert Pathlets Back to GPS
        