from datetime import date

from models.subpath import Subpath

def find_subpaths(
        city: str,
        a_longitude: float,
        a_latitude: float,
        b_longitude: float,
        b_latitude: float,
        start_date: date,
        end_date: date,
        box_half_width_m: float
) -> list[Subpath]:
    """Find the sub-paths from location A to location B in the date-range given."""
    if start_date > end_date:
        raise ValueError("start_date must be on or before end_date")
    if box_half_width_m <= 0:
        raise ValueError("box_half_width_m must be greater than 0")

    return []

