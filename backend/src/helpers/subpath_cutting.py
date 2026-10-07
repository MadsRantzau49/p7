import math
from dataclasses import dataclass
from datetime import datetime

from models.uniformed_trajectories import UniformedTrajectoryPoint
from shapely.geometry import LineString, Point, Polygon, box

EXIT_A = "exit_a"
ENTRY_B = "entry_b"
METRES_PER_DEGREE = 111_195


@dataclass
class Crossing:
    kind: str
    time: datetime
    segment_index: int
    longitude: float
    latitude: float


@dataclass
class Segment:
    index: int
    line: LineString
    start_time: datetime
    end_time: datetime


def pair_exits_with_entries(crossings: list[Crossing]) -> list[tuple[Crossing, Crossing]]:
    """Pair the corresponding exit and entry together and return a list of tuples"""
    pairs = []

    for index in range(len(crossings) - 1):
        current = crossings[index]
        following = crossings[index + 1]

        if current.kind == EXIT_A and following.kind == ENTRY_B:
            pairs.append((current, following))

    return pairs


def crossing_time(start_time: datetime, end_time: datetime, fraction: float) -> datetime:
    """Return the time at the given fraction of the way along a segment"""
    duration = end_time - start_time

    return start_time + fraction * duration


def inside_fractions(segment: LineString, area: Polygon) -> tuple[float, float] | None:
    """Return where the part of the segment inside the area starts and ends, as fractions"""
    piece = segment.intersection(area)

    if piece.is_empty or piece.geom_type != "LineString":
        return None

    first = float(segment.project(Point(piece.coords[0]), normalized=True))
    last = float(segment.project(Point(piece.coords[-1]), normalized=True))

    return min(first, last), max(first, last)


def crossings_on_segment(segment: Segment, box_a: Polygon, box_b: Polygon) -> list[Crossing]:
    """Return the exits from A and entries into B on one segment, in time order"""
    crossings = []

    if segment.line.length == 0:
        return crossings

    fractions_a = inside_fractions(segment.line, box_a)

    if fractions_a is not None:
        piece_start, piece_end = fractions_a

        if piece_end < 1:
            crossings.append(make_crossing(EXIT_A, segment, piece_end))

    fractions_b = inside_fractions(segment.line, box_b)

    if fractions_b is not None:
        piece_start, piece_end = fractions_b

        if piece_start > 0:
            crossings.append(make_crossing(ENTRY_B, segment, piece_start))

    if len(crossings) == 2 and crossings[1].time < crossings[0].time:
        crossings.reverse()

    return crossings


def crossings_on_trajectory(segments: list[Segment], box_a: Polygon, box_b: Polygon) -> list[Crossing]:
    """Return the timeline of one trip: every exit from A and entry into B, in time order"""
    timeline = []

    for segment in segments:
        found = crossings_on_segment(segment, box_a, box_b)
        timeline.extend(found)

    return timeline


def trajectory_subpaths(
    segments: list[Segment], box_a: Polygon, box_b: Polygon
) -> list[tuple[Crossing, Crossing]]:
    """Return the (exit A, enter B) pairs of one trip"""
    timeline = crossings_on_trajectory(segments, box_a, box_b)

    return pair_exits_with_entries(timeline)


def make_crossing(kind: str, segment: Segment, fraction: float) -> Crossing:
    """Build the crossing at the given fraction of the way along a segment"""
    time = crossing_time(segment.start_time, segment.end_time, fraction)
    position = segment.line.interpolate(fraction, normalized=True)

    return Crossing(kind, time, segment.index, float(position.x), float(position.y))


def build_subpath_points(
    points: list[UniformedTrajectoryPoint], exit_a: Crossing, entry_b: Crossing
) -> list[UniformedTrajectoryPoint]:
    """Return one sub-path: the exit crossing, the trip's points in between them, the entry crossing"""
    path = [
        UniformedTrajectoryPoint(
            longitude=exit_a.longitude, latitude=exit_a.latitude, point_timestamp=exit_a.time
        )
    ]

    for index in range(exit_a.segment_index + 1, entry_b.segment_index + 1):
        path.append(points[index])

    path.append(
        UniformedTrajectoryPoint(
            longitude=entry_b.longitude, latitude=entry_b.latitude, point_timestamp=entry_b.time
        )
    )

    return path


def make_box(longitude: float, latitude: float, half_width_m: float) -> Polygon:
    """Return a square box around a centre, reaching half_width_m in each direction"""
    half_height_degrees = half_width_m / METRES_PER_DEGREE
    half_width_degrees = half_width_m / (METRES_PER_DEGREE * math.cos(math.radians(latitude)))

    return box(
        longitude - half_width_degrees,
        latitude - half_height_degrees,
        longitude + half_width_degrees,
        latitude + half_height_degrees,
    )


def group_by_trajectory(rows: list[dict]) -> dict[int, list[Segment]]:
    """Turn candidate rows into segments, collected in one list per trip"""
    segments_by_trip: dict[int, list[Segment]] = {}

    for row in rows:
        line = LineString(
            [(row["start_longitude"], row["start_latitude"]), (row["end_longitude"], row["end_latitude"])]
        )
        segment = Segment(row["segment_index"], line, row["start_time"], row["end_time"])
        trajectory_id = row["trajectory_id"]

        if trajectory_id not in segments_by_trip:
            segments_by_trip[trajectory_id] = []

        segments_by_trip[trajectory_id].append(segment)

    return segments_by_trip
