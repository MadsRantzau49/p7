import math

from models.subpath import Subpath
from models.similarity import (
    BoundingBox,
    Coordinate,
    Pathlet,
    ProjectedTrajectory,
    RTreeEntry,
    RTreeNode,
    TrajectorySegments,
)

from pyproj import Transformer


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
 
    @staticmethod
    def _str_groups(items: list, max_entries: int) -> list[list]:
        """Group items (anything with a .box) into nodes using STR.
 
        With P = ceil(n / max_entries) nodes needed, the items are split into
        S = ceil(sqrt(P)) vertical slices by x, and each slice is sorted by y
        and cut into groups of max_entries. This gives roughly square nodes.
        """
        node_count = math.ceil(len(items) / max_entries)
        slice_count = math.ceil(math.sqrt(node_count))
        slice_size = slice_count * max_entries
 
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

    def FDS(
            self, 
            subpaths: list[Subpath],
            epsilon : float,
            max_entries : int
        ) -> list[Pathlet]:
        # Step 1: Projection
        projected_trajectories = self.projection(subpaths)

        #Step 2: Generate Segments
        segments = self.generate_segments(projected_trajectories)

        #Step 3: Build R-tree
        rtree = self.build_rtree(segments, epsilon, max_entries)


        #Step 4: Find Matching Segment Pairs


        #Step 5: Construct Candidate Clusters


        #Step 6: Extend Candidate Clusters


        #Step 7: Select Final Pathlets


        #Step 8: Inverse Projection
        
