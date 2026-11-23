import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.lifespan import lifespan

logger = logging.getLogger("app.access")

tags_metadata = [
    {
        "name": "Authentication",
        "description": "User registration, password authentication, JWT token rotation, and logout.",
    },
    {
        "name": "Users",
        "description": "User profile management and system-wide administrator control endpoints.",
    },
    {
        "name": "Workspaces",
        "description": "Workspace isolation and multi-tier membership management (OWNER, EDITOR, VIEWER).",
    },
    {
        "name": "Projects",
        "description": "Project organization within workspaces, tracking status and member authorization.",
    },
    {
        "name": "Tasks",
        "description": "Task lifecycle: filtering, search, sorting, pagination, and background alerts.",
    },
    {
        "name": "Labels",
        "description": "Color-coded tags scoped to projects for categorization and many-to-many attachment to tasks.",
    },
    {
        "name": "Comments",
        "description": "Task discussion threads with author ownership enforcement and workspace member visibility.",
    },
    {
        "name": "Health",
        "description": "System health check probes and uptime monitoring.",
    },
]

API_DESCRIPTION = """
## 🚀 TaskHub API — Enterprise Task & Collaboration Platform

TaskHub is a production-grade Task Management RESTful API built with **FastAPI**, **SQLAlchemy 2.x (Async)**,
and **PostgreSQL/SQLite**.

### Key Architectural Highlights:
- **Layered Clean Architecture**: Routers ➔ Service Layer ➔ Repository Layer ➔ Database Models.
- **Security & RBAC**: JWT token rotation with bcrypt; 4-tier RBAC (Admin, Workspace Owner, Editor, Viewer).
- **High-Performance Caching**: Redis-backed caching with graceful fallback and invalidation.
- **Advanced Querying**: Multi-field filtering, full-text search, dynamic sorting, and pagination.
- **Background Tasks**: Asynchronous event-driven notifications for task lifecycle events.
- **Observability**: Execution time tracking via `X-Process-Time` header and structured access logging.
- **Containerization**: Multi-stage Docker containerization and Docker Compose (FastAPI + PostgreSQL + Redis).
"""

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=API_DESCRIPTION,
    version=settings.VERSION,
    openapi_tags=tags_metadata,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    swagger_ui_parameters={
        "defaultModelsExpandDepth": -1,
        "persistAuthorization": True,
        "displayRequestDuration": True,
    },
)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Centralized handler mapping domain exceptions to HTTP JSON responses."""
    headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
        headers=headers,
    )


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = time.perf_counter() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.6f}"
    logger.info(
        "%s %s - %s (%.4fs)",
        request.method,
        request.url.path,
        response.status_code,
        process_time,
    )
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router, prefix=settings.API_V1_STR)


@app.get("/", tags=["Health"])
async def root():
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "online",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy"}
