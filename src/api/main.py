"""FastAPI application entry point."""

from fastapi import FastAPI

from .routes import router

app = FastAPI(
    title="Multi-Agent Marketing Data Scientist API",
    description="Deterministic, evidence-backed marketing investigation service.",
    version="0.2.0",
)
app.include_router(router)
