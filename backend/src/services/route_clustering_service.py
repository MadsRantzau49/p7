from helpers.similarity_steps.gps_projection_convertion import inverse_projection, projection
from helpers.similarity_steps.route_clustering.clustering import cluster_routes
from models.similarity import Route
from models.subtrajectory import Subtrajectory

from services.logging import Logging


class RouteClusteringService(Logging):
    def find_routes(
        self,
        subtrajectory_list: list[Subtrajectory] | None,
        epsilon: float,
    ) -> list[Route] | None:
        """Group subtrajectories from A to B into whole routes within epsilon metres.

        Each route is one representative polyline with the number of distinct original
        trajectories grouped into it. Projecting to metres first makes epsilon a plain distance.
        """
        if not subtrajectory_list:
            return None
        if any(len(subtrajectory.points) < 2 for subtrajectory in subtrajectory_list):
            raise ValueError("Every subtrajectory must contain at least two points.")
        self.logger.info(
            "Starting clustering: %d subtrajectories, epsilon=%.2f",
            len(subtrajectory_list),
            epsilon,
        )

        with self.log_step("Clustering total"):
            with self.log_step("Step 1: Projection"):
                projected_subtrajectories, transformer = projection(subtrajectory_list)

            with self.log_step("Step 2: Cluster routes"):
                routes = cluster_routes(projected_subtrajectories, epsilon)
                self.logger.info("Selected %d routes", len(routes))

            with self.log_step("Step 3: Inverse projection"):
                gps_routes = inverse_projection(routes, transformer)

        return gps_routes
