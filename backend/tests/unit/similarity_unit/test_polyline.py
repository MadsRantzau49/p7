from models.similarity import Polyline, ProjectedPoint


def _polyline(coordinates: list[tuple[float, float]]) -> Polyline:
    """Build a polyline from (x, y) pairs in metres."""
    return Polyline.from_points([ProjectedPoint(x, y) for x, y in coordinates])


def test_from_points_computes_segment_lengths():
    """Each segment length is the distance between two consecutive points."""
    polyline = _polyline([(0, 0), (3, 4), (3, 14)])

    assert list(polyline.segment_lengths) == [5, 10]
    assert polyline.segment_count == 2


def test_from_points_computes_cumulative_lengths_from_zero():
    """Cumulative lengths give the distance from the start at every point."""
    polyline = _polyline([(0, 0), (3, 4), (3, 14)])

    assert list(polyline.cumulative_lengths) == [0, 5, 15]
    assert polyline.total_length == 15


def test_single_point_has_no_segments_and_no_length():
    """One point is a valid polyline without any segments."""
    polyline = _polyline([(7, 7)])

    assert polyline.segment_count == 0
    assert polyline.total_length == 0


def test_duplicate_point_is_kept_as_a_zero_length_segment():
    """A stationary GPS sample stays in the polyline and adds no distance."""
    polyline = _polyline([(0, 0), (0, 0), (10, 0)])

    assert list(polyline.segment_lengths) == [0, 10]
    assert list(polyline.cumulative_lengths) == [0, 0, 10]
