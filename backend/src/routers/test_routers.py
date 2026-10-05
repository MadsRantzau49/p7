from fastapi import APIRouter
from services.trajectory_service import test_insert_trajectory_segments

router = APIRouter(prefix="/api/test")


@router.get("/segments")
async def test_create_trajectory_segments():
    """This endpoint is for testing insertion into trajectory segment table"""
    await test_insert_trajectory_segments()
