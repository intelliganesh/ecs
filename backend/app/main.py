from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.engine import Engine
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.error_logging import configure_error_logging, install_error_handlers

settings = get_settings()
configure_error_logging(settings)

# Configure the file handler before importing database and scheduler modules.
from app.db import check_database_connection, get_db
from app.report_scheduler import start_scheduler
from app.routers.retirement_builder import router as retirement_builder_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = start_scheduler(settings) if settings.scheduler_enabled else None
    try:
        yield
    finally:
        if scheduler is not None:
            await run_in_threadpool(scheduler.shutdown)


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
install_error_handlers(app)
app.include_router(retirement_builder_router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "backend"}


@app.get("/health/db", tags=["health"])
def database_health(_: Engine = Depends(get_db)) -> dict[str, str]:
    if not check_database_connection():
        return {"status": "degraded", "database": "unavailable"}
    return {"status": "ok", "database": "connected"}
