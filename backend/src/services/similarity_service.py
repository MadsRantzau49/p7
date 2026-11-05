import math

from helpers.similarity_steps.gps_projection_convertion import GpsProjectionConverter
from helpers.similarity_steps.greedy_clustering import GreedyClustering
from helpers.similarity_steps.trajectory_operations import TrajectoryOperations
from models.similarity import Pathlet
from models.subtrajectory import Subtrajectory

from services.logging import Logging


class SimilarityService(GpsProjectionConverter, GreedyClustering, TrajectoryOperations, Logging):
    def find_similar_trajectories(
        self,
        subtrajectory_list: list[Subtrajectory] | None,
        epsilon: float,
        r_tree_max_entries: int = 10,
    ) -> list[Pathlet] | None:
        """Extend continuous pathlets with an epsilon distance bound in metres.

        Every original segment is assigned exactly once. Members may support
        only part of a pathlet, with local counts in its support intervals.
        Count is distinct original trajectories contributing anywhere along it.
        r_tree_max_entries is retained for call compatibility; the extension
        engine indexes only representatives with an incremental spatial grid.
        """
        if subtrajectory_list is None:
            return None
        if not math.isfinite(epsilon) or epsilon < 0:
            raise ValueError("epsilon must be finite and non-negative.")
        if r_tree_max_entries < 2:
            raise ValueError("r_tree_max_entries must be at least 2.")
        if not subtrajectory_list:
            return []
        self.logger.info(
            "Starting clustering: %d trajectories, epsilon=%.2f",
            len(subtrajectory_list),
            epsilon,
        )

        with self.log_step("Clustering total"):
            with self.log_step("Step 1: Projection"):
                projected = self.projection(subtrajectory_list)

            with self.log_step("Step 2: Extend continuous pathlets"):
                selected = self.extend_pathlets(projected, epsilon)
                self.logger.info("Selected %d pathlets", len(selected))

            with self.log_step("Step 3: Inverse projection"):
                gps_pathlets = self.inverse_projection(selected)

        return gps_pathlets


if __name__ == "__main__":
    import json
    import logging
    from collections.abc import Iterable
    from dataclasses import asdict
    from pathlib import Path

    from helpers.trajectory_csv_parser import parse_trajectory_csv

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)-2s | %(message)s",
    )

    def parse_subpath_csv(lines: Iterable[str]) -> list[Subtrajectory]:
        """Treat each CSV route as a complete subpath for similarity processing."""
        trajectories = parse_trajectory_csv(lines)
        next_trajectory_id = 1
        for trajectory in trajectories:
            if trajectory.trajectory_id is not None:
                next_trajectory_id = max(next_trajectory_id, trajectory.trajectory_id + 1)

        subpaths = []
        for index, trajectory in enumerate(trajectories, start=1):
            trajectory_id = trajectory.trajectory_id
            if trajectory_id is None:
                trajectory_id = next_trajectory_id
                next_trajectory_id += 1

            subpaths.append(
                Subtrajectory(
                    subtrajectory_id=index,
                    trajectory_id=trajectory_id,
                    exit_a_time=trajectory.points[0].point_timestamp,
                    entry_b_time=trajectory.points[-1].point_timestamp,
                    points=trajectory.points,
                )
            )

        return subpaths

    def load_subpaths(path: str | Path) -> list[Subtrajectory]:
        """Treat each drawn route as a complete subpath, without a database lookup."""
        with Path(path).open(encoding="utf-8-sig", newline="") as fixture_file:
            return parse_subpath_csv(fixture_file)

    service = SimilarityService()

    BACKEND_DIR = Path(__file__).resolve().parents[2]
    DATA_PATH = BACKEND_DIR / "tests/data/"
    file = "aarhus_city_10000_points.csv"
    result = service.find_similar_trajectories(
        load_subpaths(f"{DATA_PATH}/trajectories/{file}"),
        300,
    )

    output_path = DATA_PATH / "pathlets.json"

    output_path.write_text(
        json.dumps(
            [asdict(pathlet) for pathlet in result or []],
            indent=2,
        ),
        encoding="utf-8",
    )
