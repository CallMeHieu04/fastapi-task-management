# FastAPI Task Management (TaskHub)

Dự án Task Management API xây dựng bằng FastAPI, SQLAlchemy 2.0 (Async), PostgreSQL/SQLite và Redis, hỗ trợ quản lý dự án, công việc theo mô hình Workspace có phân quyền RBAC.

## Yêu cầu môi trường
- Python 3.12+
- Docker & Docker Compose (tùy chọn nếu chạy container)
- `uv` (hoặc `pip`)

## Cấu hình môi trường (.env)
Tạo file `.env` từ file mẫu:
```bash
cp .env.example .env
```

Các biến môi trường chính:
- `DATABASE_URL`: Chuỗi kết nối database (mặc định dùng SQLite cho môi trường local: `sqlite+aiosqlite:///./taskhub.db`).
- `SECRET_KEY`: Khóa bí mật dùng cho JWT (tối thiểu 32 ký tự).
- `REDIS_URL`: Địa chỉ kết nối Redis (mặc định tự động fallback sang in-memory cache nếu không chạy Redis).
- `CACHE_ENABLED`: Bật hoặc tắt tính năng cache (`True` / `False`).

## Hướng dẫn chạy ứng dụng

### Cách 1: Chạy bằng Docker Compose (Khuyên dùng)
Docker compose đã cấu hình sẵn 3 services: **FastAPI App**, **PostgreSQL 16** và **Redis 7**. Khi chạy, container app sẽ tự động áp dụng migration database trước khi khởi động server.

```bash
docker compose up -d --build
```

Kiểm tra log:
```bash
docker compose logs -f app
```

Dừng hệ thống:
```bash
docker compose down
```

### Cách 2: Chạy trực tiếp trên máy (Local)

1. Tạo môi trường ảo và cài đặt thư viện:
```bash
uv venv
# Trên Windows:
.venv\Scripts\activate
# Trên Linux/macOS:
source .venv/bin/activate

uv pip install -r requirements.txt
```

2. Chạy migration database:
```bash
uv run alembic upgrade head
```

3. Khởi chạy server phát triển:
```bash
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Tài liệu API
Khi server đang chạy, truy cập tài liệu qua trình duyệt:
- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

## Kiểm thử & Code Quality
```bash
# Chạy toàn bộ test
uv run pytest

# Kiểm tra linting và formatting
uv run ruff check app tests
uv run ruff format --check app tests

# Kiểm tra static typing
uv run mypy app tests

# Kiểm tra migration database
uv run alembic check
```
