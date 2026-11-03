import math
from models.similarity import (
    BoundingBox,
    RTreeEntry,
    RTreeNode,
    TrajectorySegment,
)

class RTree:
    def center_x(self, item: RTreeEntry | RTreeNode) -> float:
        """Sort key: the x-coordinate of an item's box center."""
        return item.box.center[0]


    def center_y(self, item: RTreeEntry | RTreeNode) -> float:
        """Sort key: the y-coordinate of an item's box center."""
        return item.box.center[1]

    def _box_around(self, items):
        """MAKE DOCSTRING"""
        boxes = []
        for item in items:
            boxes.append(item.box)
        return BoundingBox.enclosing(boxes)

    def bounding_box(
        self,
        segment: TrajectorySegment,
        epsilon: float = 0,
    ) -> BoundingBox:
        """MAKE DOCSTRING"""
        return BoundingBox(
            min_x=min(segment.start.x, segment.end.x) - epsilon,
            min_y=min(segment.start.y, segment.end.y) - epsilon,
            max_x=max(segment.start.x, segment.end.x) + epsilon,
            max_y=max(segment.start.y, segment.end.y) + epsilon,
        )

    def build_rtree(
    self,
    segments: list[TrajectorySegment],
    epsilon: float,
    max_entries: int,
    ) -> RTreeNode | None:
        """MAKE DOCSTRING"""
        if not segments:
            return None

        entries = []
        for segment in segments:
            box = self.bounding_box(segment, epsilon)
            entries.append(RTreeEntry(box=box, segment=segment))

        # Make the leaves._str_groups
        nodes = []
        for group in self._str_groups(entries, max_entries):
            leaf = RTreeNode(box=self._box_around(group), entries=group)
            nodes.append(leaf)

        # Bottom up from leaves to root.
        while len(nodes) > 1:
            parents = []
            for group in self._str_groups(nodes, max_entries):
                parent = RTreeNode(box=self._box_around(group), children=group)
                parents.append(parent)
            nodes = parents
        return nodes[0]

    def query_rtree(
        self,
        root: RTreeNode | None,
        query_box: BoundingBox,
    ) -> list[TrajectorySegment]:
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


    def _str_groups(self, items: list, max_entries: int) -> list[list]:
        """MAKE DOCSTRING"""
        # Number of leafs/nodes needed, rounded up.
        node_count = math.ceil(len(items) / max_entries)

        # Width and height of the area covered by the box centres.
        min_x, min_y = items[0].box.center
        max_x, max_y = items[0].box.center
        for item in items:
            x, y = item.box.center
            min_x = min(min_x, x)
            max_x = max(max_x, x)
            min_y = min(min_y, y)
            max_y = max(max_y, y)
        width = max_x - min_x
        height = max_y - min_y

        # Number of vertical slices.
        # Wide data gets more slices and tall data fewer, keeping the groups square.
        if height == 0:
            # All centres on one horizontal line: one group per slice.
            slice_count = node_count
        elif width == 0:
            # All centres on one vertical line: a single slice.
            slice_count = 1
        else:
            slice_count = math.ceil(math.sqrt(node_count * width / height))


        slice_count = max(1, min(slice_count, node_count))

        # The amount of items per slice
        slice_size = math.ceil(node_count / slice_count) * max_entries

        # Sort everything left → right by box centre.
        by_x = sorted(items, key=self.center_x)

        # Cut into slices, sort each by y, cut into groups.
        groups = []

        # Start at 0 and jump forward by slice_size until the end.
        for start in range(0, len(by_x), slice_size):
            vertical_slice = by_x[start:start + slice_size]
            vertical_slice = sorted(vertical_slice, key=self.center_y)
            # Sort the slice bottom -> top, then cut it into groups of max_entries.
            for i in range(0, len(vertical_slice), max_entries):
                group = vertical_slice[i:i + max_entries]
                groups.append(group)

        return groups