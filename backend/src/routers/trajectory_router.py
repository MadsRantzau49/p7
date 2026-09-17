import sys

from fastapi import APIRouter
from datetime import datetime

from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from services.trajectory_service import get_trajectories

router = APIRouter(prefix="/api/trajectories")

@router.get("/get")
async def get_trajectories_endpoint(city: str, start_date: datetime | None = None, end_date: datetime | None = None, limit: int | None = None):
    return await get_trajectories(city, start_date, end_date, limit)
    