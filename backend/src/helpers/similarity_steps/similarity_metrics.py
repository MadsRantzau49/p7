import math

import numpy as np

from helpers.similarity_steps.trajectory_operations import TrajectoryOperations
from models.similarity import (
    ProjectedTrajectory,
    Projection,
    TrajectorySection,
    TrajectorySegment,
)


class SimilarityMetrics(TrajectoryOperations):
    def _spd(self, points: list[Projection], target_segments: list[TrajectorySegment]) -> float:
        """Average each source point's shortest distance to the target path."""
        total_distance = 0.0
        for point in points:
            total_distance += min(
                self.point_to_segment_distance(point, segment) for segment in target_segments
            )
        return total_distance / len(points)

    def _sspd(
        self,
        points_a: list[Projection],
        points_b: list[Projection],
        segments_a: list[TrajectorySegment],
        segments_b: list[TrajectorySegment],
    ) -> float:
        """Calculate SSPD for both two-point segments and longer paths."""
        spd_a_to_b = self._spd(points_a, segments_b)
        spd_b_to_a = self._spd(points_b, segments_a)
        return (spd_a_to_b + spd_b_to_a) / 2

    def sspd(self, segment_a: TrajectorySegment, segment_b: TrajectorySegment) -> float:
        """Compare two segments using the shared SSPD calculation."""
        return self._sspd(
            [segment_a.start, segment_a.end],
            [segment_b.start, segment_b.end],
            [segment_a],
            [segment_b],
        )

    def path_sspd(self, path_a: TrajectorySection, path_b: TrajectorySection) -> float:
        """Compare full paths using every vertex's distance to the other polyline."""
        if len(path_a.points) < 2 or len(path_b.points) < 2:
            raise ValueError("SSPD paths must contain at least two points.")

        segments_a = self.generate_segments([ProjectedTrajectory(path_a.trajectory_id, path_a.points)])
        segments_b = self.generate_segments([ProjectedTrajectory(path_b.trajectory_id, path_b.points)])

        return self._sspd(path_a.points, path_b.points, segments_a, segments_b)

    def point_to_segment_distance(self, point: Projection, segment: TrajectorySegment) -> float:
        """Return the shortest Euclidean distance to the finite original segment."""
        return self._distance_to_segment(point, segment.start, segment.end)

    def _distance_to_segment(self, point: Projection, start: Projection, end: Projection) -> float:
        """Return the shortest Euclidean distance from point to the segment start-end."""
        dx = end.x - start.x
        dy = end.y - start.y
        length_squared = dx * dx + dy * dy

        if length_squared == 0:
            return math.hypot(point.x - start.x, point.y - start.y)

        # Project onto the line, then clamp to the segment's endpoints.
        fraction = ((point.x - start.x) * dx + (point.y - start.y) * dy) / length_squared
        fraction = max(0.0, min(1.0, fraction))
        closest_x = start.x + fraction * dx
        closest_y = start.y + fraction * dy
        return math.hypot(point.x - closest_x, point.y - closest_y)

    def update_nearest(self, nearest: list[float], points: list[Projection], other_points: list[Projection]) -> float:
        """Update each point's nearest distance to the other path after both gained one point.

        Old points can only get closer through the other path's new last segment;
        the new last point is measured against every segment. Returns the average.
        """
        new_start, new_end = other_points[-2], other_points[-1]
        for index in range(len(nearest)):
            nearest[index] = min(nearest[index], self._distance_to_segment(points[index], new_start, new_end))
        nearest.append(
            min(self._distance_to_segment(points[-1], a, b) for a, b in zip(other_points, other_points[1:], strict=False))
        )
        total = 0.0
        for distance in nearest:  # same summation order as _spd, so results match path_sspd exactly
            total += distance
        return total / len(nearest)

    def _distances_to_segments(
        self,
        point_x: np.ndarray,
        point_y: np.ndarray,
        start_x: np.ndarray,
        start_y: np.ndarray,
        end_x: np.ndarray,
        end_y: np.ndarray,
    ) -> np.ndarray:
        """Array version of _distance_to_segment: element k is point k to segment k."""
        dx = end_x - start_x
        dy = end_y - start_y
        length_squared = dx * dx + dy * dy

        # Zero-length segments divide by zero here; their fraction is replaced by 0
        # below, which gives the distance to the single point, as in the scalar version.
        with np.errstate(divide="ignore", invalid="ignore"):
            fraction = ((point_x - start_x) * dx + (point_y - start_y) * dy) / length_squared
        fraction = np.where(length_squared == 0, 0.0, np.clip(fraction, 0.0, 1.0))
        closest_x = start_x + fraction * dx
        closest_y = start_y + fraction * dy
        return np.hypot(point_x - closest_x, point_y - closest_y)

    def sspd_many(self, coordinates: np.ndarray, index_a: np.ndarray, index_b: np.ndarray) -> np.ndarray:
        """SSPD for many segment pairs at once; element k compares segments index_a[k] and index_b[k].

        coordinates has one row (start_x, start_y, end_x, end_y) per segment.
        Uses the same arithmetic, in the same order, as sspd().
        """
        a = coordinates[index_a]
        b = coordinates[index_b]
        a_start_to_b = self._distances_to_segments(a[:, 0], a[:, 1], b[:, 0], b[:, 1], b[:, 2], b[:, 3])
        a_end_to_b = self._distances_to_segments(a[:, 2], a[:, 3], b[:, 0], b[:, 1], b[:, 2], b[:, 3])
        b_start_to_a = self._distances_to_segments(b[:, 0], b[:, 1], a[:, 0], a[:, 1], a[:, 2], a[:, 3])
        b_end_to_a = self._distances_to_segments(b[:, 2], b[:, 3], a[:, 0], a[:, 1], a[:, 2], a[:, 3])
        return ((a_start_to_b + a_end_to_b) / 2 + (b_start_to_a + b_end_to_a) / 2) / 2