from __future__ import annotations

import math
from array import array
from dataclasses import dataclass, field
from datetime import date, datetime, time
from itertools import pairwise

from pydantic import BaseModel


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
class ClusterMember:
    """Identity of one extracted subtrajectory grouped into a cluster.

    The exit and entry times make the reference unique, since one trajectory can produce
    several subtrajectories from A to B. The frontend sends these back to fetch a cluster's
    subtrajectories on demand.
    """

    trajectory_id: int
    exit_a_time: datetime
    entry_b_time: datetime


@dataclass
class ProjectedSubtrajectory:
    """A source subtrajectory expressed as ordered projected points.

    trajectory_id identifies the original trajectory, while exit_a_time and entry_b_time make
    the subtrajectory itself unique. Several extracted subtrajectories can share a trajectory_id.
    """

    trajectory_id: int
    exit_a_time: datetime
    entry_b_time: datetime
    projected_points: list[ProjectedPoint]

    @property
    def member(self) -> ClusterMember:
        """Return the identity of this subtrajectory for cluster membership."""
        return ClusterMember(self.trajectory_id, self.exit_a_time, self.entry_b_time)


@dataclass
class ProjectedRoute:
    """A clustered route with representative points in projected metres.

    count is the number of distinct original trajectories grouped into the route, and members
    lists every subtrajectory grouped into it.
    """

    points: list[ProjectedPoint]
    count: int
    members: list[ClusterMember] = field(default_factory=list)


@dataclass
class Route:
    """A clustered route with representative points in GPS degrees.

    count is the number of distinct original trajectories grouped into the route, and members
    lists every subtrajectory grouped into it.
    """

    points: list[GPSCoordinate]
    count: int
    members: list[ClusterMember] = field(default_factory=list)


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
class ClusteredSubtrajectory:
    """One member of a cluster: its identity and its projected polyline."""

    member: ClusterMember
    polyline: Polyline


@dataclass
class Cluster:
    """A cluster being built from the subtrajectories matched into it.

    anchor is the first subtrajectory that founded the cluster; later subtrajectories are
    matched against it. members holds every subtrajectory grouped in, the anchor included.
    """

    anchor: Polyline
    members: list[ClusteredSubtrajectory] = field(default_factory=list)


class ClusterMemberRequest(BaseModel):
    """One cluster member, as returned in a route and sent back to fetch its subtrajectory."""

    trajectory_id: int
    exit_a_time: datetime
    entry_b_time: datetime


class ClusterSubtrajectoriesRequest(BaseModel):
    """The original query plus the members of one cluster to fetch the subtrajectories for."""

    a_longitude: float
    a_latitude: float
    b_longitude: float
    b_latitude: float
    start_date: date
    end_date: date
    members: list[ClusterMemberRequest]
    box_half_width_m: float = 50
    start_time: time | None = None
    end_time: time | None = None


@dataclass
class ClusterSubtrajectory:
    """One subtrajectory of a cluster, returned when the cluster is opened on the map."""

    trajectory_id: int
    points: list[GPSCoordinate]
