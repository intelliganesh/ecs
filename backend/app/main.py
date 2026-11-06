from fastapi import Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.engine import Engine

from app.core.config import get_settings
from app.db import check_database_connection, get_db
from app.routers.retirement_builder import router as retirement_builder_router

settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(retirement_builder_router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "backend"}


@app.get("/health/db", tags=["health"])
def database_health(_: Engine = Depends(get_db)) -> dict[str, str]:
    if not check_database_connection():
        return {"status": "degraded", "database": "unavailable"}
    return {"status": "ok", "database": "connected"}
