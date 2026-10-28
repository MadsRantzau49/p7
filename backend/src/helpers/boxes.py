import math

from shapely.geometry import Polygon, box

METRES_PER_DEGREE = 111_195


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
