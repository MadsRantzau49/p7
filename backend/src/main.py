import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from routers.router import router as subtrajectory_router
from services.logging import log_heading, log_step
from starlette.middleware.base import RequestResponseEndpoint


def _configure_logging() -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_dir := os.getenv("APP_LOG_DIR"):
        path = Path(log_dir)
        path.mkdir(parents=True, exist_ok=True)
        handlers.append(
            RotatingFileHandler(
                path / "backend.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
            )
        )

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )


_configure_logging()

app = FastAPI(title="Trajectory API", version="0.0.1")
# It seems we run on different ports for frontend, so we need this for now.
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(subtrajectory_router)


@app.middleware("http")
async def log_find_routes_request(request: Request, call_next: RequestResponseEndpoint) -> Response:
    """Time find-routes requests from entry through response generation."""
    if request.method != "GET" or request.url.path != "/api/subtrajectories/get":
        return await call_next(request)

    logger = logging.getLogger("FindRoutes")
    log_heading(logger, "Find routes")
    with log_step(logger, "Find routes request"):
        response = await call_next(request)
    logger.info(
        "Response: status=%d, bytes=%s",
        response.status_code,
        response.headers.get("content-length", "unknown"),
    )
    return response


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
