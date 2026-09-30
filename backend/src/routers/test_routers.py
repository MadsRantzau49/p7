from datetime import datetime

from fastapi import APIRouter
from services.trajectory_service import test_insert_trajectory_segments

router = APIRouter(prefix="/api/test")


@router.get("/segments")
async def test_create_trajectory_segments(
    city: str,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    limit: int | None = None,
):
    """This endpoint is for testing insertion into trajectory segment table"""
    await test_insert_trajectory_segments(city, start_date, end_date, limit)
