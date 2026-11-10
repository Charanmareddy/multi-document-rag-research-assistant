"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.collections import router as collections_router, documents_router
from backend.app.core.config import get_settings
from backend.app.core.logging import configure_logging
from backend.app.database import models  # noqa: F401 - registers model metadata
from backend.app.database.session import Base, engine

settings = get_settings()
configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize local storage and database tables on startup."""

    Path("./data").mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.include_router(health_router, prefix="/api/v1")
app.include_router(collections_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
