import logging

from helpers.similarity_steps.gps_projection_convertion import inverse_projection, projection
from helpers.similarity_steps.route_clustering.clustering import (
    GridCounts,
    assign_clusters,
    build_polylines,
    build_routes,
    choose_representatives,
)
from helpers.similarity_steps.route_clustering.matching import MatchingCounts
from models.similarity import Route
from models.subtrajectory import Subtrajectory

from services.logging import Logging, describe_sizes


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
        logger = self.logger
        if not subtrajectory_list:
            logger.info("No subtrajectories to cluster")
            return None
        if any(len(subtrajectory.points) < 2 for subtrajectory in subtrajectory_list):
            raise ValueError("Every subtrajectory must contain at least two points.")

        log_workload = logger.isEnabledFor(logging.INFO)
        matching_counts = MatchingCounts() if log_workload else None
        grid_counts = GridCounts() if log_workload and epsilon > 0 else None

        with self.log_step("Clustering total"):
            with self.log_step("Step 1: Projection"):
                projected_subtrajectories, transformer = projection(subtrajectory_list)

            with self.log_step("Step 2: Build polylines"):
                entries = build_polylines(projected_subtrajectories)

            with self.log_step("Step 3: Assign clusters"):
                clusters = assign_clusters(entries, epsilon, matching_counts)

            with self.log_step("Step 4: Choose representatives"):
                representatives = choose_representatives(clusters, epsilon, grid_counts)

            with self.log_step("Step 5: Build routes"):
                routes = build_routes(clusters, representatives)

            with self.log_step("Step 6: Inverse projection"):
                gps_routes = inverse_projection(routes, transformer)

        if matching_counts is not None:
            logger.info(
                "Clustering input: epsilon=%g m, subtrajectories=%d, segments=%d; polyline lengths (m): %s",
                epsilon,
                len(entries),
                sum(entry.polyline.segment_count for entry in entries),
                describe_sizes([round(entry.polyline.total_length, 1) for entry in entries]),
            )
            logger.info(
                "Matching: anchor comparisons=%d, endpoint rejections=%d, matches=%d, "
                "full Fréchet evaluations=%d, free-space cells=%d, largest evaluation=%d cells",
                matching_counts.comparisons,
                matching_counts.endpoint_rejections,
                matching_counts.successful_matches,
                matching_counts.free_space_runs,
                matching_counts.free_space_cells,
                matching_counts.largest_free_space_cells,
            )
            if grid_counts is not None:
                logger.info(
                    "Representative grid: cell size=%g m, member-cell visits=%d, "
                    "occupied cells (summed across clusters)=%d, "
                    "peak members in one cell within a cluster=%d",
                    epsilon,
                    grid_counts.member_cell_visits,
                    grid_counts.occupied_cells_summed_across_clusters,
                    grid_counts.peak_members_in_cell_within_cluster,
                )
            sizes = [len(cluster.members) for cluster in clusters]
            logger.info(
                "Clustering output: routes=%d, singleton clusters=%d, representative points=%d; "
                "subtrajectories per cluster: %s",
                len(routes),
                sizes.count(1),
                sum(len(route.points) for route in gps_routes),
                describe_sizes(sizes),
            )
        return gps_routes
