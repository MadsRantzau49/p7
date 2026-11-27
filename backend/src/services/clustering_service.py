import logging

from helpers.similarity_steps.gps_projection_convertion import inverse_projection, projection
from helpers.similarity_steps.route_clustering.clustering import (
    assign_clusters,
    build_global_grid,
    build_polylines,
    build_routes,
    order_by_popularity,
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
        with self.log_step("Clustering total"):
            with self.log_step("Step 1: Projection"):
                projected_subtrajectories, transformer = projection(subtrajectory_list)

            with self.log_step("Step 2: Build polylines"):
                entries = build_polylines(projected_subtrajectories)

            with self.log_step("Step 3: Build global spatial grid"):
                grid = build_global_grid(entries, epsilon)

            if grid is not None and log_workload:
                logger.info(
                    "Global spatial grid: cell size=%g m, matching epsilon=%g m, "
                    "subtrajectory-cell visits=%d, occupied cells=%d, peak subtrajectories in one cell=%d",
                    grid.cell_size,
                    epsilon,
                    sum(grid.popularity.values()),
                    len(grid.popularity),
                    max(grid.popularity.values(), default=0),
                )
            elif epsilon > 0:
                logger.info("Global spatial grid skipped: within-budget cells unavailable; using input order")

            with self.log_step("Step 4: Score and sort by popularity"):
                entries = order_by_popularity(entries, grid)
            del grid  # Neither the occupied cells nor the scores are needed for matching.

            with self.log_step("Step 5: Assign clusters"):
                clusters = assign_clusters(entries, epsilon, matching_counts)

            with self.log_step("Step 6: Build routes"):
                routes = build_routes(clusters)

            with self.log_step("Step 7: Inverse projection"):
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
                "full Fréchet evaluations=%d, potential free-space cells=%d, visited=%d (%.1f%%), "
                "largest diagram=%d cells",
                matching_counts.comparisons,
                matching_counts.endpoint_rejections,
                matching_counts.successful_matches,
                matching_counts.free_space_runs,
                matching_counts.free_space_cells,
                matching_counts.visited_free_space_cells,
                100 * matching_counts.visited_free_space_cells / max(matching_counts.free_space_cells, 1),
                matching_counts.largest_free_space_cells,
            )
            logger.info(
                "Matching prefilters: skipped by start index=%d, rejected by route bounds=%d",
                matching_counts.endpoint_bucket_skips,
                matching_counts.bounds_rejections,
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
