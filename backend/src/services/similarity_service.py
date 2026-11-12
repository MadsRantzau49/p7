from helpers.similarity_steps.gps_projection_convertion import inverse_projection, projection
from helpers.similarity_steps.pathlet_extension.extension import generate_pathlet
from models.similarity import Pathlet
from models.subtrajectory import Subtrajectory

from services.logging import Logging


class SimilarityService(Logging):
    def find_similar_trajectories(
        self,
        subtrajectory_list: list[Subtrajectory] | None,
        epsilon: float,
        greedy_ranking=False,
    ) -> list[Pathlet] | None:
        """Extend continuous pathlets with an epsilon distance bound in metres.

        Every original segment is assigned exactly once. Members may support
        only part of a pathlet, with local counts in its support intervals.
        Count is distinct original trajectories contributing anywhere along it.
        r_tree_max_entries is retained for call compatibility; the extension
        engine indexes only representatives with an incremental spatial grid.
        """
        if not subtrajectory_list or subtrajectory_list is None:
            return None
        if any(len(subtrajectory.points) < 2 for subtrajectory in subtrajectory_list):
            raise ValueError("Every subtrajectory must contain at least two points.")
        self.logger.info(
            "Starting clustering: %d trajectories, epsilon=%.2f",
            len(subtrajectory_list),
            epsilon,
        )

        with self.log_step("Clustering total"):
            with self.log_step("Step 1: Projection"):
                projected_trajectories, transformer = projection(subtrajectory_list)

            with self.log_step("Step 2: Extend continuous pathlets"):
                pathlets = generate_pathlet(projected_trajectories, epsilon, greedy_ranking)
                self.logger.info("Selected %d pathlets", len(pathlets))

            with self.log_step("Step 3: Inverse projection"):
                gps_pathlets = inverse_projection(pathlets, transformer)

        return gps_pathlets
