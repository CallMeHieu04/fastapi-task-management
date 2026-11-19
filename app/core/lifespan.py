import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.cache import cache_service
from app.db.session import engine

logger = logging.getLogger("app.lifespan")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages application startup and shutdown lifecycle events."""
    logger.info(f"Starting {app.title} (v{app.version})...")
    await cache_service.init()
    yield
    logger.info(f"Stopping {app.title}... Disposing DB engine and cache.")
    await cache_service.close()
    await engine.dispose()
