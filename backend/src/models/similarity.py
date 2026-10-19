from dataclasses import dataclass, field

from models.uniformed_trajectories import UniformedTrajectoryPoint

@dataclass
class Coordinate:
    x: float
    y: float

@dataclass
class ProjectedTrajectory:
    trajectory_id: int
    projected_points: list[Coordinate]

@dataclass
class Pathlet:
    pathlet_id: int
    count: int
    trajectories_included: list[int]
    start_point: UniformedTrajectoryPoint
    end_point: UniformedTrajectoryPoint
    
@dataclass
class TrajectorySegments:
    trajectory_id: int
    segment_index: int
    start: Coordinate
    end: Coordinate

@dataclass
class BoundingBox:
    """Axis-aligned box: [min_x, max_x] x [min_y, max_y], in meters."""
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def center(self) -> tuple[float, float]:
        return ((self.min_x + self.max_x) / 2, (self.min_y + self.max_y) / 2)

    def intersects(self, other: "BoundingBox") -> bool:
        """True if the boxes overlap or touch."""
        return not (
            self.max_x < other.min_x
            or self.min_x > other.max_x
            or self.max_y < other.min_y
            or self.min_y > other.max_y
        )

    @staticmethod
    def enclosing(boxes: list["BoundingBox"]) -> "BoundingBox":
        """The smallest box that covers all the given boxes."""
        return BoundingBox(
            min_x=min(box.min_x for box in boxes),
            min_y=min(box.min_y for box in boxes),
            max_x=max(box.max_x for box in boxes),
            max_y=max(box.max_y for box in boxes),
        )

@dataclass
class RTreeEntry:
    """A segment's expanded bounding box, stored in a leaf."""
    box: BoundingBox
    segment: "TrajectorySegments"

@dataclass
class RTreeNode:
    """A leaf holds entries; an internal node holds child nodes."""
    box: BoundingBox
    entries: list[RTreeEntry] = field(default_factory=list)
    children: list["RTreeNode"] = field(default_factory=list)

    @property
    def is_leaf(self) -> bool:
        return not self.children