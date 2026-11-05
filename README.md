# TaskHub API — Task Management System

Dự án mẫu thực hành xây dựng hệ thống quản lý công việc (Task Management API) với FastAPI.

## Cấu trúc dự án (Layered Architecture)

Dự án được tổ chức theo kiến trúc phân tầng:

```
app/
├── api/             # Tầng Presentation / Routing
│   ├── deps.py      # Dependency Injection providers
│   └── v1/
│       ├── router.py
│       └── endpoints/
│           └── tasks.py
├── core/            # Cấu hình, exceptions, constants, lifespan
│   ├── config.py
│   ├── constants.py
│   ├── exceptions.py
│   └── lifespan.py
├── models/          # Domain model nội bộ
│   └── task.py
├── repositories/    # Tầng lưu trữ dữ liệu
│   └── task_repository.py
├── schemas/         # Pydantic v2 DTOs (Request / Response validation)
│   ├── common.py
│   └── task.py
├── services/        # Tầng xử lý nghiệp vụ (Business logic)
│   └── task_service.py
└── main.py          # FastAPI app instance & Exception handlers
```

## Tính năng Session 1

- Khung ứng dụng FastAPI theo mô hình phân tầng Layered Architecture.
- Quản lý vòng đời ứng dụng với `lifespan` (`@asynccontextmanager`).
- Đầy đủ CRUD API cho resource Task (`GET`, `POST`, `PATCH`, `DELETE`).
- Phân trang (`page`, `limit`) và tìm kiếm / lọc (`status`, `priority`).
- Validate dữ liệu chặt chẽ với Pydantic v2 (chặn `null` và chuỗi rỗng khi PATCH).
- Quản lý mã lỗi và thông báo tập trung qua Domain Exceptions và `constants.py`.
- Tách biệt data model nội bộ (`TaskModel`) và schema phản hồi (`TaskResponse`).

## Hướng dẫn cài đặt và chạy

### 1. Cài đặt thư viện

```bash
python -m venv .venv
source .venv/bin/activate  # Trên Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Chạy ứng dụng

```bash
uvicorn app.main:app --reload
```

- API Docs (Swagger UI): http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc
- Health check: http://127.0.0.1:8000/health

### 3. Kiểm thử và kiểm tra chất lượng mã nguồn

```bash
# Chạy unit test
pytest tests -v

# Linter và format code
ruff check app tests
ruff format app tests

# Type check
mypy app
```
