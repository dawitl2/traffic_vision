from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from .api import router
from .config import get_settings
from .database import SessionLocal, init_db
from .entities import AnalysisJob, JobStatus


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    settings.ensure_directories()
    init_db()
    with SessionLocal() as db:
        interrupted = db.scalars(select(AnalysisJob).where(AnalysisJob.status == JobStatus.processing.value)).all()
        for job in interrupted:
            job.status = JobStatus.failed.value
            job.error_message = "Backend restarted during analysis; retry this job. Completed evidence was preserved."
        db.commit()
    yield


settings = get_settings()
app = FastAPI(
    title="TrafficVision API", version="0.1.0",
    description="Local-only traffic video analysis and human-review API.", lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:5173"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)
app.include_router(router, prefix=settings.api_prefix)


@app.get("/")
def root():
    return {"name": "TrafficVision API", "docs": "/docs", "health": "/api/health"}

