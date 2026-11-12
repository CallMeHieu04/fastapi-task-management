from fastapi import APIRouter

from app.api.v1.endpoints import auth, tasks, users, workspaces

api_v1_router = APIRouter()

api_v1_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_v1_router.include_router(users.router, prefix="/users", tags=["Users"])
api_v1_router.include_router(workspaces.router, prefix="/workspaces", tags=["Workspaces"])
api_v1_router.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])
