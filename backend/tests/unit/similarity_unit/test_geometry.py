import pytest
from helpers.similarity_steps.pathlet_extension.geometry import (
    distance_along,
    dot,
    interpolate,
    point_at_fraction,
    project_onto_segment,
    squared_distance,
)
from models.similarity import Polyline, ProjectedPoint

ORIGIN = ProjectedPoint(0, 0)


def _project_onto_horizontal_segment(x: float, y: float) -> float:
    """Project a point onto the 10 m long segment from (0, 0) to (10, 0)."""
    return project_onto_segment(ProjectedPoint(x, y), ORIGIN, 10, 0, 100)


def test_dot_sign_shows_whether_vectors_agree():
    """The dot product is positive for the same direction, zero at 90 degrees, negative when opposite."""
    assert dot(1, 0, 2, 0) > 0
    assert dot(1, 0, 0, 2) == 0
    assert dot(1, 0, -2, 0) < 0
    assert dot(2, 3, 4, 5) == 23


def test_squared_distance_is_the_square_of_the_euclidean_distance():
    """A 3-4-5 triangle has a squared distance of 25."""
    assert squared_distance(0, 0, 3, 4) == 25


def test_project_onto_zero_length_segment_gives_zero():
    """A duplicate GPS point has no direction, so the fraction is always 0."""
    assert project_onto_segment(ProjectedPoint(5, 5), ORIGIN, 0, 0, 0) == 0.0


def test_point_at_fraction_returns_the_point_part_way_along():
    """Fraction 0.25 is a quarter of the way along the segment."""
    end = ProjectedPoint(8, 4)

    assert point_at_fraction(ORIGIN, end, 8, 4, 0.25) == (2, 1)


def test_point_at_fraction_returns_the_endpoints_exactly():
    """Rounding in start + dx must not move the end point, which matters when epsilon is 0."""
    start = ProjectedPoint(0.7, 0.7)
    end = ProjectedPoint(0.1, 0.1)
    dx = end.x - start.x
    dy = end.y - start.y
    assert start.x + dx != end.x  # The plain formula would miss the end point here.

    assert point_at_fraction(start, end, dx, dy, 0.0) == (0.7, 0.7)
    assert point_at_fraction(start, end, dx, dy, 1.0) == (0.1, 0.1)


def test_interpolate_works_out_the_direction_from_the_two_points():
    """Halfway between two points is their midpoint."""
    assert interpolate(ProjectedPoint(2, 2), ProjectedPoint(6, 10), 0.5) == (4, 6)


def test_distance_along_adds_earlier_segments_and_part_of_the_current_one():
    """Halfway along the second segment of an L-shape is 10 m + half of 20 m."""
    polyline = Polyline.from_points([ORIGIN, ProjectedPoint(10, 0), ProjectedPoint(10, 20)])

    assert distance_along(polyline, 1, 0.5) == pytest.approx(20)
