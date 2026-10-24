import io
from typing import Annotated

from dependencies import get_dataset_upload_service
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from helpers.trajectory_csv_parser import InvalidTrajectoryCsvError
from services.dataset_upload_service import (
    CityTimeZoneMismatchError,
    DatasetNameTakenError,
    InvalidTimeZoneError,
    UploadDataset,
)

router = APIRouter(prefix="/api/datasets")

MAX_UPLOAD_BYTES = 50 * 1024 * 1024


@router.post("/upload", status_code=201)
def upload_dataset_endpoint(
    service: Annotated[UploadDataset, Depends(get_dataset_upload_service)],
    name: Annotated[str, Form(min_length=1, max_length=50)],
    city: Annotated[str, Form(min_length=1, max_length=100)],
    time_zone: Annotated[str, Form(min_length=1, max_length=64)],
    file: Annotated[UploadFile, File()],
):
    """Upload and save a trajectory dataset."""
    if file.size is not None and file.size > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413, detail=f"file is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB"
        )

    lines = io.TextIOWrapper(file.file, encoding="utf-8-sig", newline="")

    try:
        dataset_id = service.upload_dataset(name.strip(), city.strip(), time_zone, lines)
    except InvalidTrajectoryCsvError as error:
        errors = [{"line": item.line, "message": item.message} for item in error.errors]
        raise HTTPException(status_code=422, detail=errors) from error
    except DatasetNameTakenError as error:
        raise HTTPException(status_code=409, detail=f"a dataset named '{name}' already exists") from error
    except InvalidTimeZoneError as error:
        raise HTTPException(status_code=422, detail=f"unknown time zone '{time_zone}'") from error
    except CityTimeZoneMismatchError as error:
        raise HTTPException(
            status_code=409, detail=f"the city '{error.city}' already uses the time zone '{error.time_zone}'"
        ) from error
    except UnicodeDecodeError as error:
        raise HTTPException(status_code=422, detail="file must be UTF-8 encoded") from error

    return {"dataset_id": dataset_id, "name": name.strip(), "city": city.strip()}


@router.get("/time-zones")
def get_time_zones_endpoint(
    service: Annotated[UploadDataset, Depends(get_dataset_upload_service)],
) -> list[str]:
    """List the time zones a dataset's city can use."""
    return service.get_time_zones()
