from models.subpath import Subpath
from models.similarity import TrajectoryInMeters, Pathlet


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
        