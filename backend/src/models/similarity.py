from dataclasses import dataclass, field

@dataclass
class Coordinate:
    x: float
    y: float

@dataclass
class ProjectedTrajectory:
    trajectory_id: int
    projected_points: list[Coordinate]

@dataclass
class GPSCoordinate:
    """A WGS84 geographic coordinate in degrees."""
    latitude: float
    longitude: float

@dataclass
class Pathlet:
    """A selected pathlet with all GPS points in travel order."""
    pathlet_id: int
    count: int
    trajectories_included: list[int]
    points: list[GPSCoordinate]
    
@dataclass
class TrajectorySegments:
    trajectory_id: int
    segment_index: int
    start: Coordinate
    end: Coordinate

@dataclass
class MatchingSegmentPair:
    """Two matching original segments."""
    segment_a: TrajectorySegments
    segment_b: TrajectorySegments

@dataclass
class CandidateCluster:
    """A representative, its direct matches, and contributing trajectory IDs and count."""
    representative: TrajectorySegments
    segments: list[TrajectorySegments]
    trajectories_included: list[int]
    trajectory_count: int

@dataclass
class TrajectorySection:
    """A projected path with inclusive, 0-based point indexes in its original trajectory."""
    trajectory_id: int
    start_index: int
    end_index: int
    points: list[Coordinate]

@dataclass
class ExtendedPathletCandidate:
    """A representative path and the trajectory sections assigned to it."""
    representative: TrajectorySection
    sections: list[TrajectorySection]
    trajectories_included: list[int]
    trajectory_count: int

@dataclass
class ProjectedPathlet:
    """A selected representative and its newly covered sections, in meters."""
    pathlet_id: int
    representative: TrajectorySection
    sections: list[TrajectorySection]
    trajectories_included: list[int]
    count: int

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
