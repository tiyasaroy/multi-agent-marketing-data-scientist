"""FastAPI application entry point and browser dashboard."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .routes import router

app = FastAPI(
    title="Multi-Agent Marketing Data Scientist API",
    description="Deterministic, evidence-backed marketing investigation service.",
    version="0.2.0",
)
app.include_router(router)

STATIC_DIR = Path(__file__).with_name("static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
