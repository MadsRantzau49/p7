from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.dataset_router import router as dataset_router
from routers.trajectory_router import router as trajectory_router

app = FastAPI(title="Trajectory API", version="0.0.1")

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(trajectory_router)
app.include_router(dataset_router)


@app.get("/")
def root():
    return {"message": "Test"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
