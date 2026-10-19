import io
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from helpers.subpath_csv_parser import parse_subpath_csv
from helpers.trajectory_csv_parser import InvalidTrajectoryCsvError
from models.similarity import Pathlet
from services.similarity_service import SimilarityService, configure_logging, log_step, logger

router = APIRouter(prefix="/api/similarity", tags=["Similarity"])
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


@router.post("/fds", response_model=list[Pathlet])
def run_fds(
    file: Annotated[UploadFile, File()],
    epsilon: Annotated[float, Form(ge=0, allow_inf_nan=False)] = 2000,
    max_entries: Annotated[int, Form(ge=2)] = 4,
) -> list[Pathlet]:
    """Load CSV routes as subpaths and return FDS GPS pathlets."""
    if file.size is not None and file.size > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="file is larger than 50 MB")

    configure_logging()
    logger.info(
        "Received FDS CSV upload: %s bytes, epsilon=%s, max_entries=%s", file.size, epsilon, max_entries
    )
    try:
        with log_step("Load uploaded CSV subpaths"):
            with io.TextIOWrapper(file.file, encoding="utf-8-sig", newline="") as lines:
                subpaths = parse_subpath_csv(lines)
        return SimilarityService().FDS(subpaths, epsilon, max_entries)
    except InvalidTrajectoryCsvError as error:
        errors = [{"line": item.line, "message": item.message} for item in error.errors]
        raise HTTPException(status_code=422, detail=errors) from error
    except UnicodeDecodeError as error:
        raise HTTPException(status_code=422, detail="file must be UTF-8 encoded") from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
