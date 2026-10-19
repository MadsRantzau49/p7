import logging
from contextlib import contextmanager
from pathlib import Path
from time import perf_counter

from pyproj import Transformer

from models.similarity import Coordinate, ProjectedTrajectory, TrajectorySegments
from models.subpath import Subpath


# Choose "DEBUG", "INFO", "WARNING", or "ERROR".
LOG_LEVEL = "INFO"
LOG_FILE = Path(__file__).resolve().parents[2] / "similarity_service.log"

# Use logger.debug(...), logger.info(...), logger.warning(...), or logger.error(...).
logger = logging.getLogger("similarity_service")


def configure_logging() -> None:
    """Send service logs to both the console and an appended log file."""
    logger.setLevel(LOG_LEVEL)
    logger.propagate = False
    if logger.handlers:
        return

    formatter = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s")
    console_handler = logging.StreamHandler()
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")

    for handler in (console_handler, file_handler):
        handler.setFormatter(formatter)
        logger.addHandler(handler)


@contextmanager
def log_step(name: str):
    """Log a step's elapsed time, including a traceback if it fails."""
    configure_logging()
    started = perf_counter()
    logger.info("%s started", name)
    try:
        yield
    except Exception:
        logger.exception("%s failed after %.6f s", name, perf_counter() - started)
        raise
    else:
        logger.info("%s finished in %.6f s", name, perf_counter() - started)


class SimilarityService:

    def projection(
        self,
        trajectories: list[Subpath],
    ) -> list[ProjectedTrajectory]:

        if not trajectories:
            raise ValueError("Projection requires at least one trajectory.")

        # Collect all points so one projection can be used for every trajectory.
        points = []

        for trajectory in trajectories:
            if not trajectory.points:
                raise ValueError("Each trajectory must contain at least one point.")

            for point in trajectory.points:
                points.append(point)

        # Choose a UTM zone based on the centre of the input data.
        # This is suitable when the trajectories cover a local or regional area.
        centre_latitude = sum(point.latitude for point in points) / len(points)
        centre_longitude = sum(point.longitude for point in points) / len(points)

        utm_zone = int((centre_longitude + 180) / 6) + 1
        epsg_code = (32600 if centre_latitude >= 0 else 32700) + utm_zone
        logger.debug("Projecting %d points using UTM zone %d (EPSG:%d)", len(points), utm_zone, epsg_code)

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

    def FDS(self, subpaths: list[Subpath]) -> None:
        """Run FDS with timings for each implemented step and the total runtime."""
        configure_logging()
        started = perf_counter()
        logger.info("Running FDS on %d subpaths", len(subpaths))
        try:
            with log_step("Step 1: Projection"):
                projected_trajectories = self.projection(subpaths)
            logger.debug("Projected %d trajectories", len(projected_trajectories))

            with log_step("Step 2: Generate segments"):
                segments = self.generate_segments(projected_trajectories)
            logger.info("Generated %d segments", len(segments))

            # Step 3: Build R-tree

            # Step 4: Find Matching Segment Pairs

            # Step 5: Construct Candidate Clusters

            # Step 6: Extend Candidate Clusters

            # Step 7: Select Final Pathlets

            # Step 8: Inverse Projection
        finally:
            logger.info("FDS total elapsed: %.6f s", perf_counter() - started)

        return None


def debug_fds() -> None:
    """Run FDS on the manually drawn Skagen-to-Aalborg CSV fixture."""
    configure_logging()
    started = perf_counter()
    logger.info("Writing logs to %s (level: %s)", LOG_FILE, LOG_LEVEL)

    try:
        with log_step("Load CSV subpaths"):
            from trajectory_builder.importer import load_subpaths

            fixture = Path(__file__).resolve().parents[2] / "tests/data/trajectories/skagen_to_aalborg.csv"
            subpaths = load_subpaths(fixture)
        logger.info("Loaded %d subpaths from %s", len(subpaths), fixture)
        result = SimilarityService().FDS(subpaths)
        logger.info("FDS result: %s", result)
    finally:
        logger.info("Debug run total elapsed: %.6f s", perf_counter() - started)


if __name__ == "__main__":
    debug_fds()
