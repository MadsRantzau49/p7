from fastapi import FastAPI
from routers.trajectory_router import router as trajectory_router


app = FastAPI(
    title="Trajectory API",
    version="0.0.1"
)

app.include_router(trajectory_router)

@app.get("/")
def root():
    return {"message": "Test"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )