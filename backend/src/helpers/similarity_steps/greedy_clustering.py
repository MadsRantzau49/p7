import math
from array import array
from collections import defaultdict
from dataclasses import dataclass, field
from statistics import median

from models.similarity import (
    ProjectedPathlet,
    ProjectedTrajectory,
    Projection,
    SupportInterval,
    TrajectorySection,
)


@dataclass(slots=True)
class _Polyline:
    points: list[Projection]
    lengths: array
    offsets: array

    @classmethod
    def from_points(cls, points: list[Projection]) -> "_Polyline":
        lengths = array("d")
        offsets = array("d", [0.0])
        for a, b in zip(points, points[1:], strict=False):
            length = math.hypot(b.x - a.x, b.y - a.y)
            lengths.append(length)
            offsets.append(offsets[-1] + length)
        return cls(points, lengths, offsets)


@dataclass(slots=True)
class _Backbone:
    line: _Polyline
    sections: list[TrajectorySection] = field(default_factory=list)


@dataclass(slots=True)
class _Seed:
    backbone: int
    edge: int
    fraction: float
    distance_squared: float


@dataclass(slots=True)
class _Match:
    backbone: int
    end: int
    start_m: float
    end_m: float
    direction: int


@dataclass(slots=True)
class _IndexedEdge:
    backbone: int
    edge: int
    start: Projection
    end: Projection
    dx: float
    dy: float
    squared: float
    left: float
    right: float
    bottom: float
    top: float


class _BackboneIndex:
    """Incremental spatial grid over representatives, not the entire input dataset."""

    def __init__(self, epsilon: float, cell_size: float) -> None:
        self.epsilon = epsilon
        self.cell_size = cell_size
        self.cells: dict[tuple[int, int], list[_IndexedEdge]] = defaultdict(list)
        self.long_edges: list[_IndexedEdge] = []

    def add(self, backbone_index: int, line: _Polyline) -> None:
        for edge, (a, b) in enumerate(zip(line.points, line.points[1:], strict=False)):
            dx, dy = b.x - a.x, b.y - a.y
            item = _IndexedEdge(
                backbone_index, edge, a, b, dx, dy, dx * dx + dy * dy,
                min(a.x, b.x) - self.epsilon, max(a.x, b.x) + self.epsilon,
                min(a.y, b.y) - self.epsilon, max(a.y, b.y) + self.epsilon,
            )
            left = math.floor(item.left / self.cell_size)
            right = math.floor(item.right / self.cell_size)
            bottom = math.floor(item.bottom / self.cell_size)
            top = math.floor(item.top / self.cell_size)
            # Sparse, very long edges use a fallback list, so indexing a
            # diagonal never allocates a huge rectangle of mostly empty cells.
            if (right - left + 1) * (top - bottom + 1) > 256:
                self.long_edges.append(item)
                continue
            for x in range(left, right + 1):
                for y in range(bottom, top + 1):
                    self.cells[x, y].append(item)

    def seeds(self, point: Projection) -> list[_Seed]:
        cell = (math.floor(point.x / self.cell_size), math.floor(point.y / self.cell_size))
        nearby = self.cells.get(cell, [])
        seeds = []
        epsilon_squared = self.epsilon * self.epsilon
        for items in (nearby, self.long_edges):
            for item in items:
                if point.x < item.left or point.x > item.right or point.y < item.bottom or point.y > item.top:
                    continue
                a, b = item.start, item.end
                fraction = (
                    ((point.x - a.x) * item.dx + (point.y - a.y) * item.dy) / item.squared
                    if item.squared else 0.0
                )
                if fraction < 0:
                    fraction = 0.0
                elif fraction > 1:
                    fraction = 1.0
                if fraction <= 0:
                    x, y = a.x, a.y
                elif fraction >= 1:
                    x, y = b.x, b.y
                else:
                    x, y = a.x + fraction * item.dx, a.y + fraction * item.dy
                distance_x, distance_y = point.x - x, point.y - y
                distance_squared = distance_x * distance_x + distance_y * distance_y
                if distance_squared <= epsilon_squared:
                    seeds.append(_Seed(item.backbone, item.edge, fraction, distance_squared))
        return seeds


def _position(a: Projection, b: Projection, fraction: float) -> tuple[float, float]:
    # Use exact original vertices at boundaries, including epsilon == 0.
    if fraction <= 0:
        return a.x, a.y
    if fraction >= 1:
        return b.x, b.y
    return a.x + fraction * (b.x - a.x), a.y + fraction * (b.y - a.y)


class GreedyClustering:
    def extend_pathlets(
        self, trajectories: list[ProjectedTrajectory], epsilon: float,
    ) -> list[ProjectedPathlet]:
        """Grow long representatives and consume continuous, partially supporting sections.

        Matching cursors move monotonically along the two polylines, adapting
        their pace to different sampling and lengths. Every traversed reference
        corner is checked inside the source segment. Only whole source segments
        are committed, so every original segment is assigned exactly once.
        """
        lines = [_Polyline.from_points(trajectory.projected_points) for trajectory in trajectories]
        sample = [length for line in lines[:32] for length in line.lengths if length > 0]
        cell_size = max(epsilon, median(sample) if sample else 1.0, 1.0)
        index = _BackboneIndex(epsilon, cell_size)
        backbones: list[_Backbone] = []
        epsilon_squared = epsilon * epsilon
        for section_index in sorted(range(len(lines)), key=lambda i: -lines[i].offsets[-1]):
            line = lines[section_index]
            start = 0
            pending = None
            while start < len(line.lengths):
                match = pending or self._find_match(line, start, index, backbones, epsilon_squared)
                pending = None
                if match is not None:
                    backbones[match.backbone].sections.append(
                        self._section(
                            trajectories, section_index, start, match.end,
                            min(match.start_m, match.end_m), max(match.start_m, match.end_m),
                            match.direction == -1,
                        )
                    )
                    start = match.end
                    continue

                # Extend an unmatched representative until a genuine match
                # begins. Supporter changes never split an existing backbone.
                end = start + 1
                while end < len(line.lengths):
                    pending = self._find_match(line, end, index, backbones, epsilon_squared)
                    if pending is not None:
                        break
                    end += 1
                backbone_line = _Polyline.from_points(line.points[start : end + 1])
                own_section = self._section(
                    trajectories, section_index, start, end, 0.0, backbone_line.offsets[-1], False,
                )
                index.add(len(backbones), backbone_line)
                backbones.append(_Backbone(backbone_line, [own_section]))
                start = end

            if len(line.lengths) == 0 and line.points:
                own_section = self._section(trajectories, section_index, 0, 0, 0.0, 0.0, False)
                backbones.append(_Backbone(line, [own_section]))

        return [
            ProjectedPathlet(
                representative=backbone.sections[0],
                sections=backbone.sections,
                count=len({section.trajectory_id for section in backbone.sections}),
                support=self._support_intervals(backbone.sections, backbone.line.offsets[-1]),
            )
            for backbone in backbones
        ]

    def _find_match(
        self, source: _Polyline, start: int, index: _BackboneIndex,
        backbones: list[_Backbone], epsilon_squared: float,
    ) -> _Match | None:
        seeds = index.seeds(source.points[start])
        if not seeds:
            return None
        source_a, source_b = source.points[start], source.points[start + 1]
        source_dx, source_dy = source_b.x - source_a.x, source_b.y - source_a.y
        source_squared = source_dx * source_dx + source_dy * source_dy

        def priority(seed: _Seed) -> tuple[bool, bool, bool, float]:
            line = backbones[seed.backbone].line
            a, b = line.points[seed.edge], line.points[seed.edge + 1]
            dx, dy = b.x - a.x, b.y - a.y
            dot = dx * source_dx + dy * source_dy
            position = line.offsets[seed.edge] + seed.fraction * line.lengths[seed.edge]
            available = line.offsets[-1] - position if dot >= 0 else position
            # Prefer a continuing, similarly directed corridor over a crossing
            # or a nearby dead endpoint, which would consume only tiny pieces.
            dead_end = available < source.lengths[start] / 2
            crossing = dot * dot < 0.5 * source_squared * (dx * dx + dy * dy)
            return len(line.lengths) < 2, dead_end, crossing, seed.distance_squared

        # Extend the first continuous match directly; generating competing long
        # candidates would repeat most of the accepted geometry comparisons.
        for seed in sorted(seeds, key=priority):
            reference = backbones[seed.backbone].line
            a, b = reference.points[seed.edge], reference.points[seed.edge + 1]
            dot = (b.x - a.x) * (source_b.x - source_a.x) + (b.y - a.y) * (source_b.y - source_a.y)
            preferred = 1 if dot >= 0 else -1
            for direction in (preferred, -preferred):
                match = self._advance(
                    source, start, reference, seed, direction, epsilon_squared,
                )
                if match is not None:
                    return match
        return None

    @staticmethod
    def _advance(
        source: _Polyline, start: int, reference: _Polyline,
        seed: _Seed, direction: int, epsilon_squared: float,
    ) -> _Match | None:
        edge, fraction = seed.edge, seed.fraction
        start_m = reference.offsets[edge] + fraction * reference.lengths[edge]
        current_m = start_m
        end = start
        epsilon = math.sqrt(epsilon_squared)
        for source_edge in range(start, len(source.lengths)):
            a, b = source.points[source_edge], source.points[source_edge + 1]
            candidate = edge
            best_distance = math.inf
            next_edge, next_fraction = edge, fraction
            reach = source.lengths[source_edge] + 2 * epsilon
            while 0 <= candidate < len(reference.lengths):
                p, q = reference.points[candidate], reference.points[candidate + 1]
                dx, dy = q.x - p.x, q.y - p.y
                squared = dx * dx + dy * dy
                projected = ((b.x - p.x) * dx + (b.y - p.y) * dy) / squared if squared else 0.0
                if projected < 0:
                    projected = 0.0
                elif projected > 1:
                    projected = 1.0
                if candidate == edge:
                    if direction == 1 and projected < fraction or direction == -1 and projected > fraction:
                        projected = fraction
                if projected <= 0:
                    x, y = p.x, p.y
                elif projected >= 1:
                    x, y = q.x, q.y
                else:
                    x, y = p.x + projected * dx, p.y + projected * dy
                distance_x, distance_y = b.x - x, b.y - y
                distance = distance_x * distance_x + distance_y * distance_y
                if distance < best_distance:
                    best_distance = distance
                    next_edge, next_fraction = candidate, projected
                elif squared:
                    break
                candidate += direction
                boundary = candidate if direction == 1 else candidate + 1
                if 0 <= boundary < len(reference.offsets):
                    if abs(reference.offsets[boundary] - current_m) > reach:
                        break
            if best_distance > epsilon_squared:
                break
            next_m = reference.offsets[next_edge] + next_fraction * reference.lengths[next_edge]
            advance = abs(next_m - current_m)
            # Reference corners are breakpoints of the continuous matching.
            # Between them both paths are straight, so endpoint bounds certify
            # the complete geometry, not only its sampled observations.
            corners = range(edge + 1, next_edge + 1) if direction == 1 else range(edge, next_edge, -1)
            valid = True
            for corner in corners:
                along = abs(reference.offsets[corner] - current_m) / advance if advance else 0.0
                x, y = _position(a, b, along)
                point = reference.points[corner]
                distance_x, distance_y = x - point.x, y - point.y
                if distance_x * distance_x + distance_y * distance_y > epsilon_squared:
                    valid = False
                    break
            if not valid:
                break
            edge, fraction, current_m = next_edge, next_fraction, next_m
            end = source_edge + 1
        return _Match(seed.backbone, end, start_m, current_m, direction) if end > start else None

    @staticmethod
    def _section(
        trajectories: list[ProjectedTrajectory], section_index: int, start: int, end: int,
        representative_start: float, representative_end: float, reversed_direction: bool,
    ) -> TrajectorySection:
        trajectory = trajectories[section_index]
        return TrajectorySection(
            trajectory_id=trajectory.trajectory_id,
            start_index=start,
            end_index=end,
            points=trajectory.projected_points[start : end + 1],
            section_index=section_index,
            representative_start_m=representative_start,
            representative_end_m=representative_end,
            reversed=reversed_direction,
        )

    @staticmethod
    def _support_intervals(sections: list[TrajectorySection], total_length: float) -> list[SupportInterval]:
        by_trajectory: dict[int, list[tuple[float, float]]] = defaultdict(list)
        for section in sections:
            by_trajectory[section.trajectory_id].append(
                (section.representative_start_m, section.representative_end_m)
            )
        if total_length == 0:
            return [SupportInterval(0.0, 0.0, len(by_trajectory))]
        events: dict[float, int] = defaultdict(int)
        for intervals in by_trajectory.values():
            start, end = min(intervals)
            for next_start, next_end in sorted(intervals)[1:]:
                if next_start <= end:
                    end = max(end, next_end)
                else:
                    events[start] += 1
                    events[end] -= 1
                    start, end = next_start, next_end
            events[start] += 1
            events[end] -= 1
        support: list[SupportInterval] = []
        previous = 0.0
        count = 0
        for position, change in sorted(events.items()):
            if position > previous:
                if support and support[-1].count == count:
                    support[-1].end_m = position
                else:
                    support.append(SupportInterval(previous, position, count))
            count += change
            previous = position
        return support
