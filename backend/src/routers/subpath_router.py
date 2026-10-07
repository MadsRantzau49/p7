from datetime import date

from fastapi import APIRouter, HTTPException
from models.subpath import Subpath
from services.subpath_service import find_subpaths

router = APIRouter(prefix="/api/subpaths")


@router.get("/get", response_model=list[Subpath])
def get_subpaths(
    a_longitude: float,
    a_latitude: float,
    b_longitude: float,
    b_latitude: float,
    start_date: date,
    end_date: date,
    box_half_width_m: float = 50,
):
    """Return the sub-paths from location A to location B in the date-range given."""
    try:
        return find_subpaths(
            a_longitude,
            a_latitude,
            b_longitude,
            b_latitude,
            start_date,
            end_date,
            box_half_width_m,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
