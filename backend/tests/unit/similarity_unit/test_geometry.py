from helpers.similarity_steps.route_clustering.geometry import polyline_cells
from models.similarity import Polyline, ProjectedPoint

ORIGIN = ProjectedPoint(0, 0)


def test_polyline_cells_cover_a_segment_without_gaps():
    """A 25 m segment over 10 m cells touches columns 0, 1 and 2 with no cell skipped."""
    polyline = Polyline.from_points([ORIGIN, ProjectedPoint(25, 0)])

    cells = polyline_cells(polyline, 10)

    assert cells == {(0, 0), (1, 0), (2, 0)}
