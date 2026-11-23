from fastapi import APIRouter

from app.api.v1.endpoints import auth, comments, labels, projects, tasks, users, workspaces

api_v1_router = APIRouter()

api_v1_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_v1_router.include_router(users.router, prefix="/users", tags=["Users"])
api_v1_router.include_router(workspaces.router, prefix="/workspaces", tags=["Workspaces"])
api_v1_router.include_router(projects.router, tags=["Projects"])
api_v1_router.include_router(tasks.router, tags=["Tasks"])
api_v1_router.include_router(labels.router, tags=["Labels"])
api_v1_router.include_router(comments.router, tags=["Comments"])
