from __future__ import annotations

import math
from array import array
from dataclasses import dataclass, field
from itertools import pairwise


@dataclass
class GPSCoordinate:
    """Geographic latitude and longitude, both expressed in degrees."""

    latitude: float
    longitude: float


@dataclass
class ProjectedPoint:
    """Cartesian x and y coordinates in the shared projected system, in metres."""

    x: float
    y: float


@dataclass
class ProjectedTrajectory:
    """One input A-to-B subpath expressed as ordered projected points."""

    subtrajectory_id: int
    projected_points: list[ProjectedPoint]


@dataclass
class SupportInterval:
    """A distance interval with a constant number of supporting input subpaths.

    start_m and end_m are measured along the representative from its start.
    count is the number of distinct subtrajectory IDs covering the interval's
    interior. A zero-length representative uses the interval [0.0, 0.0] and
    counts all subtrajectory IDs assigned to it.
    """

    start_m: float
    end_m: float
    count: int


@dataclass
class TrajectorySection:
    """One A-to-B passage's contribution to a representative.

    subtrajectory_id identifies the passage whose points the source indices
    select (both ends inclusive). Representative offsets are arc lengths in
    metres from the representative's start, stored with start <= end.
    """

    subtrajectory_id: int
    representative_start_m: float
    representative_end_m: float
    source_start_index: int
    source_end_index: int


@dataclass
class ProjectedPathlet:
    """A completed pathlet with representative points in projected metres.

    count is the number of distinct input subpaths with positive-length
    coverage anywhere along it. For a zero-length pathlet, all assigned source
    subtrajectory IDs count. support contains local counts over metre intervals;
    these can be smaller than the overall count.
    """

    points: list[ProjectedPoint]
    count: int
    support: list[SupportInterval] = field(default_factory=list)
    sections: list[TrajectorySection] = field(default_factory=list)
    distances_m: list[float] = field(default_factory=list)


@dataclass
class Pathlet:
    """A completed pathlet with representative points in GPS degrees.

    count and support retain the coverage semantics of ProjectedPathlet.
    Support interval offsets remain in metres after inverse projection.
    distances_m contains the projected arc length of each representative point,
    allowing the frontend to split the geometry at exact support boundaries.
    """

    points: list[GPSCoordinate]
    count: int
    support: list[SupportInterval] = field(default_factory=list)
    sections: list[TrajectorySection] = field(default_factory=list)
    distances_m: list[float] = field(default_factory=list)


@dataclass
class TrajectoryLine:
    """A projected input prepared for matching, with cached polyline lengths.

    subtrajectory_id identifies the input subpath for counting and inspection.
    """

    subtrajectory_id: int
    polyline: Polyline


@dataclass
class Match:
    """An accepted source run and its positions along a representative."""

    representative: Representative
    end_index: int
    start_m: float
    end_m: float


@dataclass
class Polyline:
    """Points of a trajectory plus precomputed lengths.

    Segment j runs from points[j] to points[j + 1].

    segment_lengths[j]     length of segment j (n - 1 values for n points)
    cumulative_lengths[j]  distance along the polyline at point j (n values, starting at 0)
    """

    points: list[ProjectedPoint]
    segment_lengths: array
    cumulative_lengths: array

    @classmethod
    def from_points(cls, points: list[ProjectedPoint]) -> Polyline:
        """Build a polyline, computing every segment length and the running total once."""
        segment_lengths = array("d")
        cumulative_lengths = array("d", [0.0])
        for start, end in pairwise(points):
            length = math.hypot(end.x - start.x, end.y - start.y)
            segment_lengths.append(length)
            cumulative_lengths.append(cumulative_lengths[-1] + length)
        return cls(points, segment_lengths, cumulative_lengths)

    @property
    def segment_count(self) -> int:
        """Number of segments (one fewer than the number of points)."""
        return len(self.segment_lengths)

    @property
    def total_length(self) -> float:
        """Length of the whole polyline, in metres."""
        return self.cumulative_lengths[-1]


@dataclass
class IndexedSegment:
    """One representative segment with values precomputed for the seed search.

    The box is the segment's bounding box grown by epsilon on every side (the expanded
    bounding box): any point within epsilon of the segment lies inside it.
    """

    representative: Representative
    segment_index: int
    start: ProjectedPoint
    end: ProjectedPoint
    dx: float
    dy: float
    length_squared: float
    min_x: float
    max_x: float
    min_y: float
    max_y: float


@dataclass
class Seed:
    """A representative segment within epsilon of a point: a possible start of a match.

    `fraction` is the spot on the segment closest to the point.
    """

    segment: IndexedSegment
    fraction: float
    distance_squared: float

    @property
    def representative(self) -> Representative:
        """Representative that owns the candidate segment."""
        return self.segment.representative

    @property
    def segment_index(self) -> int:
        """Candidate segment's index within the representative's polyline."""
        return self.segment.segment_index


@dataclass
class Representative:
    """A representative polyline, the section it was made from, and the sections matched to it.

    own_section is the stretch of trajectory the representative was created from.
    assigned_sections are the stretches of other trajectories (or of the same one) that were
    matched to it later.
    """

    polyline: Polyline
    own_section: TrajectorySection
    assigned_sections: list[TrajectorySection] = field(default_factory=list)
