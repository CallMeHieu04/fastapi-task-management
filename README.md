# TaskHub — Hệ thống quản lý công việc (Task Management API)

> **Dự án thực hành tốt nghiệp / Đào tạo IT Training (Sun* Talent Incubator Vietnam)**  
> Tuân thủ 100% các tiêu chí đặc tả kĩ thuật và 14 tính năng bắt buộc trong tài liệu yêu cầu.

---

## 1. Tổng quan Kiến trúc và Công nghệ (Tech Stack)

- **Framework**: FastAPI (>= 0.111.0)
- **ORM / Database**: SQLAlchemy 2.x Async (`async_sessionmaker`, DeclarativeBase, Mapped types)
- **Migration Tool**: Alembic (async mode configured)
- **Data Validation & Schemas**: Pydantic v2 (`ConfigDict`, `@field_validator`, generic pagination)
- **Cache & Blacklist**: Redis 7 (với cơ chế In-memory Fallback tự động khi chạy dev độc lập)
- **Database Engine**: PostgreSQL 16 trong Docker Compose (kèm async SQLite khi chạy local nhanh)
- **Security & RBAC**: JWT Access Token (HS256) + Refresh Token (hỗ trợ thu hồi / blacklist), Bcrypt password hashing
- **Background Tasks**: FastAPI BackgroundTasks (Async Email notification khi assign task)
- **Code Quality**: Ruff lint 100% pass, Mypy type-checking 0 errors
- **Containerization**: Dockerfile đa tầng & `docker-compose.yml` (App + PostgreSQL 16 + Redis 7)

---

## 2. Cấu trúc thư mục (Layered Architecture)

```
thuctap/
├── app/
│   ├── api/                      # Tầng Presentation / Routing
│   │   ├── deps.py               # Dependency Injection (Auth, DB, Services, Pagination)
│   │   └── v1/
│   │       ├── router.py         # Router trung tâm nạp tất cả sub-routers
│   │       └── endpoints/
│   │           ├── auth.py       # Register, Login, Refresh, Logout
│   │           ├── users.py      # Profile, Update (PATCH), Change password
│   │           ├── workspaces.py # Workspace CRUD, Member management
│   │           ├── projects.py   # Project CRUD, Archive, Task list, Label list
│   │           ├── tasks.py      # Task detail, Update, Assign, Labels, Comments
│   │           └── comments.py   # Delete comments
│   ├── core/                     # Cấu hình, bảo mật, cache & background worker
│   │   ├── config.py             # Quản lý cấu hình bằng Pydantic BaseSettings
│   │   ├── security.py           # Hash mật khẩu bcrypt, tạo và giải mã JWT
│   │   ├── cache.py              # Dịch vụ Redis Cache & In-memory Fallback
│   │   ├── notifications.py      # Background worker gửi email khi assign task
│   │   └── lifespan.py           # Quản lý Lifespan startup/shutdown (@asynccontextmanager)
│   ├── db/                       # Kết nối Database
│   │   ├── base.py               # SQLAlchemy DeclarativeBase
│   │   └── session.py            # create_async_engine & async_sessionmaker
│   ├── models/                   # 8 thực thể dữ liệu ORM chuẩn hóa
│   │   ├── enums.py              # UserRole, WorkspaceMemberRole, ProjectStatus, TaskStatus, TaskPriority
│   │   ├── user.py               # Entity: users
│   │   ├── workspace.py          # Entities: workspaces, workspace_members
│   │   ├── project.py            # Entity: projects
│   │   ├── task.py               # Entities: tasks, task_labels (m-n association)
│   │   ├── label.py              # Entity: labels
│   │   └── comment.py            # Entity: comments
│   ├── schemas/                  # Pydantic v2 DTOs (Request / Response validation)
│   │   ├── common.py             # PaginatedResponse, PaginationMeta, MessageResponse
│   │   ├── token.py              # Token, TokenPayload, RefreshTokenRequest
│   │   ├── user.py               # UserCreate, UserLogin, UserUpdate, UserResponse
│   │   ├── workspace.py          # WorkspaceCreate, WorkspaceUpdate, WorkspaceResponse, MemberAdd
│   │   ├── project.py            # ProjectCreate, ProjectUpdate, ProjectResponse
│   │   ├── task.py               # TaskCreate, TaskUpdate, TaskResponse, TaskFilterParams
│   │   ├── label.py              # LabelCreate, LabelResponse
│   │   └── comment.py            # CommentCreate, CommentResponse
│   ├── repositories/             # Data Access Layer (Truy vấn SQLAlchemy Async)
│   │   ├── user_repository.py
│   │   ├── workspace_repository.py
│   │   ├── project_repository.py
│   │   ├── task_repository.py
│   │   ├── label_repository.py
│   │   └── comment_repository.py
│   ├── services/                 # Business Logic & RBAC Enforcement Layer
│   │   ├── auth_service.py
│   │   ├── user_service.py
│   │   ├── workspace_service.py
│   │   ├── project_service.py
│   │   ├── task_service.py
│   │   ├── label_service.py
│   │   └── comment_service.py
│   └── main.py                   # FastAPI instance, CORS, OpenAPI Docs & Lifespan
├── alembic/                      # Database migrations với Alembic async
├── tests/
│   ├── conftest.py               # Pytest async fixture & TestClient cô lập
│   └── test_taskhub.py           # Bộ test kiểm thử toàn diện
├── Dockerfile                    # Container image tối ưu Python 3.12
├── docker-compose.yml            # Khởi chạy full stack (App + PostgreSQL 16 + Redis 7)
├── pyproject.toml                # Cấu hình Ruff & Mypy
├── pytest.ini                    # Cấu hình Pytest Asyncio
├── requirements.txt              # Danh sách thư viện phụ thuộc
├── run.py                        # Script chạy nhanh ứng dụng
└── README.md
```

---

## 3. Danh sách 14 Tính Năng Bắt Buộc Đã Hoàn Thành

| # | Tính năng | Trạng thái | Chi tiết triển khai |
| :---: | :--- | :---: | :--- |
| **1** | **Auth** |  Đạt | `POST /api/v1/auth/register`, `login` (JWT access + refresh token), `refresh` (quay vòng token), `logout` (thu hồi refresh token vào blacklist). |
| **2** | **User Profile** |  Đạt | `GET /api/v1/users/me`, `PATCH /api/v1/users/me`, `POST /api/v1/users/me/change-password`. |
| **3** | **Workspace CRUD & Members** |  Đạt | `POST /workspaces` (người tạo là OWNER), `GET /workspaces/{id}`, `PATCH /workspaces/{id}` (OWNER only), `DELETE /workspaces/{id}` (OWNER only), `POST /{id}/members` (invite), `DELETE /{id}/members/{user_id}`. |
| **4** | **Project Management** |  Đạt | CRUD project trong workspace, `PATCH /projects/{id}/archive` chuyển trạng thái sang ARCHIVED. Phân quyền OWNER/EDITOR. |
| **5** | **Task Management** |  Đạt | CRUD task trong project, gán `assignee_id`, cập nhật trạng thái (`TODO`, `IN_PROGRESS`, `IN_REVIEW`, `DONE`), mức độ ưu tiên (`LOW`, `MEDIUM`, `HIGH`, `URGENT`), ngày hết hạn (`due_date`). |
| **6** | **Label Management** |  Đạt | CRUD nhãn theo project, mã màu Hex (`#FF5733`), gán nhãn `POST /tasks/{id}/labels/{label_id}`, gỡ nhãn `DELETE /tasks/{id}/labels/{label_id}`. |
| **7** | **Comment System** |  Đạt | Thêm bình luận `POST /tasks/{id}/comments`, xem danh sách bình luận trên task, xóa bình luận `DELETE /comments/{id}` (tác giả hoặc Admin). |
| **8** | **Filtering & Pagination** |  Đạt | Lọc task linh hoạt theo `status`, `priority`, `assignee_id`, phân trang `page` & `limit`, trả về metadata `total`, `page`, `page_size`, `total_pages`. |
| **9** | **Redis Caching & Invalidation** |  Đạt | Cache danh sách task `GET /projects/{id}/tasks` với TTL 120s; tự động xóa cache khi tạo mới, sửa, xóa task hoặc đổi nhãn. |
| **10** | **Background Tasks** |  Đạt | Dùng FastAPI `BackgroundTasks` gửi email notification bất đồng bộ cho thành viên khi được giao task mới hoặc đổi người phụ trách. |
| **11** | **Phân quyền RBAC chặt chẽ** |  Đạt | Phân quyền 4 cấp: `ADMIN` (toàn quyền hệ thống), `OWNER` (toàn quyền workspace/thành viên), `EDITOR` (tạo/sửa dự án & task), `VIEWER` (chỉ xem, chặn sửa xóa 403). |
| **12** | **Swagger / ReDoc UI** |  Đạt | Tích hợp sẵn nút **Authorize Bearer Token** trên Swagger UI; mô tả chi tiết schema phản hồi lỗi 400, 401, 403, 404, 422. |
| **13** | **Docker Compose Stack** |  Đạt | `docker-compose.yml` khởi chạy trọn gói: `app` + `taskhub-db` (PostgreSQL 16) + `taskhub-redis` (Redis 7) với health check tự động. |
| **14** | **Code Quality Standard** |  Đạt | **Ruff lint pass 100%**, **Mypy pass 100% không có lỗi type**. |

---

## 4. Hướng dẫn cài đặt và khởi chạy

### Cách 1: Chạy trực tiếp trên máy (Local Development)

Môi trường ảo `.venv` đã được tạo sẵn trong thư mục dự án:

1. **Kích hoạt virtual environment**:
   ```powershell
   .venv\Scripts\activate
   ```

2. **Khởi chạy ứng dụng**:
   ```powershell
   python run.py
   ```
   *(Hoặc: `uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`)*

3. **Mở trình duyệt truy cập tài liệu API**:
   - **Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
   - **ReDoc UI**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
   - **Health check**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---

### Cách 2: Chạy toàn bộ hệ thống bằng Docker Compose

Khởi chạy cả 3 dịch vụ (FastAPI App, PostgreSQL 16 và Redis 7):

```powershell
docker compose up --build -d
```

- Xem log hoạt động:
  ```powershell
  docker compose logs -f app
  ```
- Dừng toàn bộ stack:
  ```powershell
  docker compose down
  ```

---

## 5. Kiểm tra chất lượng mã nguồn & Kiểm thử tự động

### 1. Chạy Ruff Linter
```powershell
.venv\Scripts\ruff check app tests
```
*Kết quả: **All checks passed!***

### 2. Chạy Mypy Type Checker
```powershell
.venv\Scripts\mypy app
```
*Kết quả: **Success: no issues found in 49 source files***

### 3. Chạy Pytest
```powershell
.venv\Scripts\python -m pytest tests -v
```
*Kết quả: **4/4 passed (100% Passed)***
