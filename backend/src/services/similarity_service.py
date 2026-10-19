import math

from models.subpath import Subpath
from models.similarity import (
    BoundingBox,
    CandidateCluster,
    Coordinate,
    MatchingSegmentPair,
    Pathlet,
    ProjectedTrajectory,
    RTreeEntry,
    RTreeNode,
    TrajectorySegments,
)
import logging
from contextlib import contextmanager
from pathlib import Path
from time import perf_counter

from pyproj import Transformer


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
    
    def bounding_box(
        self,
        segment: TrajectorySegments,
        epsilon: float = 0,
    ) -> BoundingBox:
        """Box around a segment, grown by epsilon meters on every side.
 
        epsilon=0 gives the original box BB; epsilon>0 gives EBB_epsilon.
        """
        return BoundingBox(
            min_x=min(segment.start.x, segment.end.x) - epsilon,
            min_y=min(segment.start.y, segment.end.y) - epsilon,
            max_x=max(segment.start.x, segment.end.x) + epsilon,
            max_y=max(segment.start.y, segment.end.y) + epsilon,
        )
    
    def build_rtree(
    self,
    segments: list[TrajectorySegments],
    epsilon: float,
    max_entries: int,
    ) -> RTreeNode | None:
        """Build an R-tree over the segments' expanded bounding boxes (Step 3).
 
        Uses Sort-Tile-Recursive (STR) packing: boxes are sorted by x into
        vertical slices, each slice is sorted by y and packed into nodes of
        up to max_entries. The same packing is repeated level by level
        until one root remains. Returns None when there are no segments.
        """
        if max_entries < 2:
            raise ValueError("max_entries must be at least 2.")
        if not segments:
            return None

        #TODO make this a full for-loop
        entries = [
            RTreeEntry(box=self.bounding_box(segment, epsilon), segment=segment)
            for segment in segments
        ]
 
        # Leaves: STR-pack the segment boxes.
        nodes = [
            RTreeNode(
                box=BoundingBox.enclosing([entry.box for entry in group]),
                entries=group,
            )
            for group in self._str_groups(entries, max_entries)
        ]
 
        # Upper levels: STR-pack the node boxes until one root remains.
        while len(nodes) > 1:
            nodes = [
                RTreeNode(
                    box=BoundingBox.enclosing([child.box for child in group]),
                    children=group,
                )
                for group in self._str_groups(nodes, max_entries)
            ]
 
        return nodes[0]
 
    def query_rtree(
        self,
        root: RTreeNode | None,
        query_box: BoundingBox,
    ) -> list[TrajectorySegments]:
        """Return segments whose stored (expanded) box intersects query_box."""
        if root is None:
            return []
 
        results = []
        stack = [root]
 
        while stack:
            node = stack.pop()
            if not node.box.intersects(query_box):
                continue  # Nothing below this node can match.
 
            if node.is_leaf:
                results.extend(
                    entry.segment
                    for entry in node.entries
                    if entry.box.intersects(query_box)
                )
            else:
                stack.extend(node.children)
 
        return results

    def point_to_segment_distance(self, point: Coordinate, segment: TrajectorySegments) -> float:
        """Return the shortest Euclidean distance to the finite original segment."""
        dx = segment.end.x - segment.start.x
        dy = segment.end.y - segment.start.y
        length_squared = dx * dx + dy * dy

        if length_squared == 0:
            return math.hypot(point.x - segment.start.x, point.y - segment.start.y)

        # Project onto the line, then clamp to the segment's endpoints.
        fraction = (
            (point.x - segment.start.x) * dx + (point.y - segment.start.y) * dy
        ) / length_squared
        fraction = max(0.0, min(1.0, fraction))
        closest_x = segment.start.x + fraction * dx
        closest_y = segment.start.y + fraction * dy
        return math.hypot(point.x - closest_x, point.y - closest_y)

    def sspd(self, segment_a: TrajectorySegments, segment_b: TrajectorySegments) -> float:
        """Average the two directed endpoint-to-segment distances (SSPD)."""
        spd_a_to_b = (
            self.point_to_segment_distance(segment_a.start, segment_b)
            + self.point_to_segment_distance(segment_a.end, segment_b)
        ) / 2
        spd_b_to_a = (
            self.point_to_segment_distance(segment_b.start, segment_a)
            + self.point_to_segment_distance(segment_b.end, segment_a)
        ) / 2
        return (spd_a_to_b + spd_b_to_a) / 2

    def find_matching_segment_pairs(
        self,
        segments: list[TrajectorySegments],
        root: RTreeNode | None,
        epsilon: float,
    ) -> list[MatchingSegmentPair]:
        """Find cross-trajectory pairs passing the R-tree and SSPD tests (Step 4).

        The tree stores epsilon-expanded boxes. Queries use original boxes,
        and distance calculations use the original segment coordinates.
        """
        if epsilon < 0:
            raise ValueError("epsilon must be non-negative.")

        matches = []
        candidate_count = 0
        for segment in segments:
            query_box = self.bounding_box(segment)
            candidates = self.query_rtree(root, query_box)
            for candidate in candidates:
                # i < k excludes the same trajectory and counts each pair once.
                if segment.trajectory_id >= candidate.trajectory_id:
                    continue

                candidate_count += 1
                distance = self.sspd(segment, candidate)
                if distance <= epsilon:
                    matches.append(
                        MatchingSegmentPair(
                            segment_a=segment,
                            segment_b=candidate,
                        )
                    )

        logger.debug("Checked %d candidate pairs; found %d matches", candidate_count, len(matches))
        return matches

    def construct_candidate_clusters(
        self,
        segments: list[TrajectorySegments],
        matching_pairs: list[MatchingSegmentPair],
    ) -> list[CandidateCluster]:
        """Build one cluster around each segment using only direct matches (Step 5)."""
        members_by_segment = {}
        for segment in segments:
            key = (segment.trajectory_id, segment.segment_index)
            members_by_segment[key] = {key: segment}

        # Add each match in both directions. Segment keys prevent duplicate members.
        for pair in matching_pairs:
            key_a = (pair.segment_a.trajectory_id, pair.segment_a.segment_index)
            key_b = (pair.segment_b.trajectory_id, pair.segment_b.segment_index)
            members_by_segment[key_a][key_b] = pair.segment_b
            members_by_segment[key_b][key_a] = pair.segment_a

        clusters = []
        for representative in segments:
            key = (representative.trajectory_id, representative.segment_index)
            members = list(members_by_segment[key].values())
            trajectory_ids = {member.trajectory_id for member in members}
            clusters.append(
                CandidateCluster(
                    representative=representative,
                    segments=members,
                    trajectories_included=list(trajectory_ids),
                    trajectory_count=len(trajectory_ids),
                )
            )

        return clusters
 
    @staticmethod
    def _str_groups(items: list, max_entries: int) -> list[list]:
        """Group items (anything with a .box) into nodes using shape-aware STR."""
        node_count = math.ceil(len(items) / max_entries)

        centres = [item.box.center for item in items]
        width = max(x for x, _ in centres) - min(x for x, _ in centres)
        height = max(y for _, y in centres) - min(y for _, y in centres)

        if height == 0:
            slice_count = node_count
        elif width == 0:
            slice_count = 1
        else:
            slice_count = math.ceil(math.sqrt(node_count * width / height))
        slice_count = max(1, min(slice_count, node_count))

        slice_size = math.ceil(node_count / slice_count) * max_entries

        by_x = sorted(items, key=lambda item: item.box.center[0])

        groups = []
        for start in range(0, len(by_x), slice_size):
            vertical_slice = sorted(
                by_x[start:start + slice_size],
                key=lambda item: item.box.center[1],
            )
            groups.extend(
                vertical_slice[i:i + max_entries]
                for i in range(0, len(vertical_slice), max_entries)
            )
        return groups

    def FDS(self, subpaths: list[Subpath], epsilon : float,
                max_entries : int) -> None:
        """Run FDS with timings for each implemented step and the total runtime."""
        configure_logging()
        started = perf_counter()
        logger.info("Running FDS on %d subpaths", len(subpaths))
        try:
            with log_step("Step 1: Projection"):
                # Step 1: Projection
                projected_trajectories = self.projection(subpaths)
            logger.debug("Projected %d trajectories", len(projected_trajectories))

            with log_step("Step 2: Generate segments"):
                # Step 2: Genereate Segments
                segments = self.generate_segments(projected_trajectories)
            logger.info("Generated %d segments", len(segments))

            #Step 3: Build R-tree
            rtree = self.build_rtree(segments, epsilon, max_entries)
            # Step 3: Build R-tree

            # Step 4: Find Matching Segment Pairs
            with log_step("Step 4: Find matching segment pairs"):
                matching_pairs = self.find_matching_segment_pairs(segments, rtree, epsilon)
            logger.info("Found %d matching segment pairs", len(matching_pairs))

            # Step 5: Construct Candidate Clusters
            with log_step("Step 5: Construct candidate clusters"):
                candidate_clusters = self.construct_candidate_clusters(segments, matching_pairs)
            logger.info("Constructed %d candidate clusters", len(candidate_clusters))

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
        result = SimilarityService().FDS(subpaths, 2000, 4)
        logger.info("FDS result: %s", result)
    finally:
        logger.info("Debug run total elapsed: %.6f s", perf_counter() - started)


if __name__ == "__main__":
    debug_fds()
