from helpers.similarity_steps.gps_projection_convertion import inverse_projection, projection
from helpers.similarity_steps.route_clustering.clustering import (
    assign_clusters,
    build_polylines,
    build_routes,
    choose_representatives,
)
from models.similarity import Route
from models.subtrajectory import Subtrajectory

from services.logging import Logging


class ClusteringService(Logging):
    def find_routes(
        self,
        subtrajectory_list: list[Subtrajectory] | None,
        epsilon: float,
    ) -> list[Route] | None:
        """Group subtrajectories from A to B into whole routes within epsilon metres.

        Each route is one representative polyline with the number of distinct original
        trajectories grouped into it. Projecting to metres first makes epsilon a plain distance.
        """
        self.log_heading()
        if not subtrajectory_list:
            return None
        if any(len(subtrajectory.points) < 2 for subtrajectory in subtrajectory_list):
            raise ValueError("Every subtrajectory must contain at least two points.")

        with self.log_step("Clustering total"):
            with self.log_step("Step 1: Projection"):
                projected_subtrajectories, transformer = projection(subtrajectory_list)

            with self.log_step("Step 2: Build polylines"):
                entries = build_polylines(projected_subtrajectories)

            with self.log_step("Step 3: Assign clusters"):
                clusters = assign_clusters(entries, epsilon)

            with self.log_step("Step 4: Choose representatives"):
                representatives = choose_representatives(clusters, epsilon)

            with self.log_step("Step 5: Build routes"):
                routes = build_routes(clusters, representatives)

            with self.log_step("Step 6: Inverse projection"):
                gps_routes = inverse_projection(routes, transformer)

        return gps_routes
