"""Spatial index for matching trajectories to representative segments.

Only representative geometry is indexed. Assigned source sections contribute
support without becoming additional geometry for matching.
"""

import math

from helpers.similarity_steps.pathlet_extension.geometry import (
    box_contains,
    point_at_fraction,
    project_onto_segment,
    squared_distance,
)
from models.similarity import IndexedSegment, ProjectedPoint, Representative, Seed

MAX_CELLS_PER_SEGMENT = 256


class RepresentativeGrid:
    """Find nearby representative segments using a uniform grid of square cells.

    Each segment's bounding box is expanded by epsilon and indexed in every
    cell it touches. Queries inspect their own cell and a separate list of
    segments whose expanded boxes exceed MAX_CELLS_PER_SEGMENT.
    """

    def __init__(self, epsilon: float, cell_size: float) -> None:
        self.epsilon = epsilon
        self.epsilon_squared = epsilon * epsilon
        self.cell_size = cell_size
        self.cells: dict[tuple[int, int], list[IndexedSegment]] = {}
        self.long_segments: list[IndexedSegment] = []

    def cell_coordinate(self, value: float) -> int:
        """Return the cell index for a coordinate, using floor to handle negatives."""
        return math.floor(value / self.cell_size)

    def add(self, representative: Representative) -> None:
        """Index every segment of a new representative.

        Expand each segment's bounding box by epsilon and store its cached
        record in every cell touched by that box. Records exceeding
        MAX_CELLS_PER_SEGMENT are stored in long_segments instead.

        Add each representative once and keep its geometry unchanged while indexed.
        """
        points = representative.polyline.points
        for segment_index in range(len(points) - 1):
            segment = self._indexed_segment(
                representative,
                segment_index,
                points[segment_index],
                points[segment_index + 1],
            )
            first_column = self.cell_coordinate(segment.min_x)
            last_column = self.cell_coordinate(segment.max_x)
            first_row = self.cell_coordinate(segment.min_y)
            last_row = self.cell_coordinate(segment.max_y)
            cell_count = (last_column - first_column + 1) * (last_row - first_row + 1)
            if cell_count > MAX_CELLS_PER_SEGMENT:
                self.long_segments.append(segment)
                continue
            for column in range(first_column, last_column + 1):
                for row in range(first_row, last_row + 1):
                    self.cells.setdefault((column, row), []).append(segment)

    def seeds_near(self, point: ProjectedPoint) -> list[Seed]:
        """Return candidate match starts within epsilon metres of the query point.

        Search the point's grid cell together with all long_segments. First
        reject candidates outside their expanded bounding boxes, then project
        the point onto each remaining segment and check its squared distance.

        Each seed contains the segment, closest fraction, and squared distance.
        Results are unranked; the matching step determines their priority.
        """
        cell = (self.cell_coordinate(point.x), self.cell_coordinate(point.y))
        seeds = []

        for candidates in (self.cells.get(cell, []), self.long_segments):
            for segment in candidates:
                if not box_contains(segment, point):
                    continue
                fraction = project_onto_segment(
                    point,
                    segment.start,
                    segment.dx,
                    segment.dy,
                    segment.length_squared,
                )
                x, y = point_at_fraction(segment.start, segment.end, segment.dx, segment.dy, fraction)

                distance_squared = squared_distance(point.x, point.y, x, y)
                if distance_squared <= self.epsilon_squared:
                    seeds.append(Seed(segment, fraction, distance_squared))
        return seeds

    def _indexed_segment(
        self,
        representative: Representative,
        segment_index: int,
        start: ProjectedPoint,
        end: ProjectedPoint,
    ) -> IndexedSegment:
        """Build a segment record with cached geometry for spatial queries.

        Store the endpoints, displacement, squared length, and bounding box
        expanded by epsilon. segment_index locates it within the representative.
        """
        dx, dy = end.x - start.x, end.y - start.y
        return IndexedSegment(
            representative=representative,
            segment_index=segment_index,
            start=start,
            end=end,
            dx=dx,
            dy=dy,
            length_squared=dx * dx + dy * dy,
            min_x=min(start.x, end.x) - self.epsilon,
            max_x=max(start.x, end.x) + self.epsilon,
            min_y=min(start.y, end.y) - self.epsilon,
            max_y=max(start.y, end.y) + self.epsilon,
        )
