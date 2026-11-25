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
    {"name": "Authentication", "description": "Đăng ký, đăng nhập và quản lý JWT token."},
    {"name": "Users", "description": "Thông tin người dùng và quyền admin."},
    {"name": "Workspaces", "description": "Quản lý workspace và phân quyền thành viên."},
    {"name": "Projects", "description": "Quản lý project trong workspace."},
    {"name": "Tasks", "description": "CRUD task, tìm kiếm, lọc, phân trang và background task."},
    {"name": "Labels", "description": "Quản lý nhãn công việc theo project."},
    {"name": "Comments", "description": "Bình luận trong task."},
    {"name": "Health", "description": "Kiểm tra trạng thái hệ thống."},
]

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.VERSION,
    openapi_tags=tags_metadata,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    swagger_ui_parameters={
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
