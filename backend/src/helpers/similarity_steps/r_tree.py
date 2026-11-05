import numpy as np
import shapely
from shapely import STRtree

from models.similarity import TrajectorySegment


class RTree:
    def _segment_bounds(
        self,
        segments: list[TrajectorySegment],
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Return the tight bounding box of every segment as four arrays.

        Position i in each array (min_x, min_y, max_x, max_y) belongs to segments[i].
        """
        coordinates = np.array(
            [[segment.start.x, segment.start.y, segment.end.x, segment.end.y] for segment in segments],
            dtype=float,
        )
        min_x = np.minimum(coordinates[:, 0], coordinates[:, 2])
        min_y = np.minimum(coordinates[:, 1], coordinates[:, 3])
        max_x = np.maximum(coordinates[:, 0], coordinates[:, 2])
        max_y = np.maximum(coordinates[:, 1], coordinates[:, 3])
        return min_x, min_y, max_x, max_y

    def build_rtree(
        self,
        segments: list[TrajectorySegment],
        epsilon: float,
        max_entries: int,
    ) -> STRtree | None:
        """Build an STR-packed R-tree over every segment's epsilon-expanded box (Step 3).

        Tree item i is the bounding box of segments[i], grown by epsilon on every
        side. Queries then use the tight (unexpanded) boxes, so two boxes overlap
        whenever an endpoint of one segment lies within epsilon of the other's box.
        That is always true for pairs with SSPD <= epsilon, so the filter never
        drops a real match.

        Args:
            segments: Segments from Step 2, in metres.
            epsilon: Matching distance in metres; must be non-negative.
            max_entries: Maximum children per tree node (shapely's node_capacity).

        Returns:
            The tree, or None when there are no segments.
        """
        if epsilon < 0:
            raise ValueError("epsilon must be non-negative.")
        if max_entries < 2:
            raise ValueError("max_entries must be at least 2.")
        if not segments:
            return None

        min_x, min_y, max_x, max_y = self._segment_bounds(segments)
        expanded_boxes = shapely.box(
            min_x - epsilon,
            min_y - epsilon,
            max_x + epsilon,
            max_y + epsilon,
        )
        return STRtree(expanded_boxes, node_capacity=max_entries)

    def query_rtree(
        self,
        tree: STRtree | None,
        segments: list[TrajectorySegment],
    ) -> tuple[np.ndarray, np.ndarray]:
        """Find every (query, stored) pair of overlapping boxes in one batched query.

        Pair k means the tight box of segments[query_index[k]] intersects the
        stored, epsilon-expanded box of segments[tree_index[k]]. Touching boxes
        count as overlapping. The result includes self pairs and both directions
        of every pair; the caller filters those. Pairs are sorted by query
        index, then tree index, so the output order is stable.

        Args:
            tree: The tree from build_rtree, built from the same segments list.
            segments: The same list, in the same order, that built the tree.

        Returns:
            Two equal-length integer arrays (query_index, tree_index).
        """
        if tree is None:
            empty = np.array([], dtype=np.intp)
            return empty, empty

        min_x, min_y, max_x, max_y = self._segment_bounds(segments)
        query_boxes = shapely.box(min_x, min_y, max_x, max_y)
        query_index, tree_index = tree.query(query_boxes)

        order = np.lexsort((tree_index, query_index))
        return query_index[order], tree_index[order]