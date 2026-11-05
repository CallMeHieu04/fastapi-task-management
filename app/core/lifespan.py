import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.cache import cache_service
from app.db.base import Base
from app.db.session import engine

logger = logging.getLogger("app.lifespan")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan event handler for TaskHub.

    - Initializes database tables
    - Initializes Redis cache connection
    - Cleans up connections on shutdown
    """
    logger.info("Initializing TaskHub database schema...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Connecting to cache service...")
    await cache_service.init()

    logger.info(f"TaskHub API '{app.title}' (version {app.version}) is ready to accept requests.")

    yield

    logger.info("Shutting down TaskHub API...")
    await cache_service.close()
    await engine.dispose()
    logger.info("TaskHub shutdown complete.")
