import io
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from services.dataset_upload_service import (
    DatasetNameTaken,
    UploadRejected,
    upload_dataset,
)

router = APIRouter(prefix="/api/datasets")

MAX_UPLOAD_BYTES = 50 * 1024 * 1024


@router.post("/upload", status_code=201)
def upload_dataset_endpoint(
    name: Annotated[str, Form(min_length=1, max_length=50)], file: Annotated[UploadFile, File()]
):
    if file.size is not None and file.size > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413, detail=f"file is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB"
        )

    lines = io.TextIOWrapper(file.file, encoding="utf-8-sig", newline="")

    try:
        dataset_id = upload_dataset(name.strip(), lines)
    except UploadRejected as error:
        errors = [{"line": item.line, "message": item.message} for item in error.errors]
        raise HTTPException(status_code=422, detail=errors) from error
    except DatasetNameTaken as error:
        raise HTTPException(
            status_code=409, detail=f"a dataset or city named '{name}' already exists"
        ) from error
    except UnicodeDecodeError as error:
        raise HTTPException(status_code=422, detail="file must be UTF-8 encoded") from error

    return {"dataset_id": dataset_id, "name": name.strip()}
