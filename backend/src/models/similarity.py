from dataclasses import dataclass, field


@dataclass(slots=True)
class Projection:
    x: float
    y: float


@dataclass
class ProjectedTrajectory:
    trajectory_id: int
    projected_points: list[Projection]


@dataclass
class GPSCoordinate:
    latitude: float
    longitude: float


@dataclass(slots=True)
class SupportInterval:
    """Distinct source trajectories supporting this arc-length interval, in projected metres."""

    start_m: float
    end_m: float
    count: int


@dataclass
class Pathlet:
    """Extended original geometry; count is distinct trajectories contributing anywhere along it."""

    points: list[GPSCoordinate]
    count: int
    support: list[SupportInterval] = field(default_factory=list)


@dataclass
class TrajectorySegment:
    trajectory_id: int
    segment_index: int
    start: Projection
    end: Projection
    # Position of the input section, independent of its original trajectory ID.
    section_index: int = 0


@dataclass
class SegmentCluster:
    """Disjoint assignments: each member and its orientation relative to the representative."""

    representative: TrajectorySegment
    members: list[tuple[TrajectorySegment, int]]


@dataclass
class MatchingSegmentPair:
    """Two matching original segments."""

    segment_a: TrajectorySegment
    segment_b: TrajectorySegment


@dataclass
class CandidateCluster:
    representative: TrajectorySegment
    segments: list[TrajectorySegment]


@dataclass(slots=True)
class TrajectorySection:
    trajectory_id: int
    start_index: int
    end_index: int
    points: list[Projection]
    section_index: int = 0
    representative_start_m: float = 0.0
    representative_end_m: float = 0.0
    reversed: bool = False


@dataclass
class ProjectedPathlet:
    """An extended representative with disjoint source assignments and partial-support intervals."""

    representative: TrajectorySection
    sections: list[TrajectorySection]
    count: int
    support: list[SupportInterval] = field(default_factory=list)


@dataclass
class ExtendedPathletCandidate:
    representative: TrajectorySection
    sections: list[TrajectorySection]


@dataclass
class BoundingBox:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def center(self) -> tuple[float, float]:
        """Get center of a bounding box."""
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
    box: BoundingBox
    segment: TrajectorySegment


@dataclass
class RTreeNode:
    box: BoundingBox
    entries: list[RTreeEntry] = field(default_factory=list)
    children: list["RTreeNode"] = field(default_factory=list)

    @property
    def is_leaf(self) -> bool:
        """Return whether a node is a leaf."""
        return not self.children
