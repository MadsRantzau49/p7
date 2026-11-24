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
class ProjectedSubtrajectory:
    """A source subtrajectory expressed as ordered projected points.

    trajectory_id identifies the original trajectory. Several extracted
    subtrajectories can share the same trajectory_id.
    """

    trajectory_id: int
    projected_points: list[ProjectedPoint]


@dataclass
class ProjectedRoute:
    """A clustered route with representative points in projected metres.

    count is the number of distinct original trajectories grouped into the route.
    """

    points: list[ProjectedPoint]
    count: int


@dataclass
class Route:
    """A clustered route with representative points in GPS degrees.

    count is the number of distinct original trajectories grouped into the route.
    """

    points: list[GPSCoordinate]
    count: int


@dataclass
class Polyline:
    """Points of a route plus precomputed lengths.

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
class Representative:
    """A representative route polyline and the trajectories grouped into it.

    members holds the distinct original trajectory IDs assigned to this route,
    including the one it was created from.
    """

    polyline: Polyline
    members: set[int] = field(default_factory=set)
