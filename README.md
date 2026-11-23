# 🚀 TaskHub — Enterprise Task & Collaboration Platform API

[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0%20Async-D71F00.svg?logo=sqlalchemy&logoColor=white)](https://www.sqlalchemy.org/)
[![Docker](https://img.shields.io/badge/Docker-Multi--Stage-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com/)
[![Redis](https://img.shields.io/badge/Redis-Cache%20Layer-DC382D.svg?logo=redis&logoColor=white)](https://redis.io/)
[![Code Style: Ruff](https://img.shields.io/badge/Code%20Style-Ruff-black.svg)](https://github.com/astral-sh/ruff)
[![Type Checked: Mypy](https://img.shields.io/badge/Type%20Checked-Mypy-blue.svg)](https://mypy-lang.org/)

**TaskHub** is a production-grade, asynchronous RESTful API engineered for collaborative project and task management. Built with **FastAPI**, **SQLAlchemy 2.x Async**, and **PostgreSQL/SQLite**, TaskHub incorporates strict layered clean architecture, enterprise-grade Role-Based Access Control (RBAC), multi-layer caching with automatic fallback, and event-driven background tasks.

---

## 📑 Table of Contents
- [Architecture & Design](#-architecture--design)
- [Core Features](#-core-features)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Quick Start: Docker Setup (Recommended)](#-quick-start-docker-setup-recommended)
- [Local Development Setup](#-local-development-setup)
- [Environment Variables](#-environment-variables)
- [API Documentation](#-api-documentation)
- [Testing & Quality Assurance](#-testing--quality-assurance)

---

## 🏛 Architecture & Design

TaskHub strictly follows the **Layered Clean Architecture** pattern to guarantee testability, maintainability, and clean separation of concerns:

```
                  ┌───────────────────────────────┐
                  │      HTTP Clients / SPA       │
                  └───────────────┬───────────────┘
                                  │ HTTP / JSON
                                  ▼
                  ┌───────────────────────────────┐
                  │    FastAPI Routers (Endpoints)│
                  └───────────────┬───────────────┘
                                  │ Dependency Injection
                                  ▼
                  ┌───────────────────────────────┐
                  │    Service Layer (Domain)     │  ◄── Caching & BackgroundTasks
                  └───────────────┬───────────────┘
                                  │
                                  ▼
                  ┌───────────────────────────────┐
                  │   Repository Layer (Data)     │
                  └───────────────┬───────────────┘
                                  │ SQLAlchemy 2.x Async
                                  ▼
             ┌────────────────────┴────────────────────┐
             │                                         │
             ▼                                         ▼
   ┌───────────────────┐                     ┌───────────────────┐
   │ PostgreSQL / DB   │                     │   Redis Caching   │
   └───────────────────┘                     └───────────────────┘
```

1. **API Routers (`app/api/`)**: Handle HTTP serialization, OpenAPI schema documentation, parameter validation, and dependency injection (`Depends`).
2. **Service Layer (`app/services/`)**: Enforces business logic, domain validations, RBAC ownership checks, read-through caching, and background task dispatching.
3. **Repository Layer (`app/repositories/`)**: Encapsulates database queries using SQLAlchemy 2.x async select statements.
4. **Data Models & Schemas (`app/models/`, `app/schemas/`)**: SQLAlchemy declarative models with Alembic migrations and Pydantic v2 schemas for request validation.

---

## ✨ Core Features

### 🔐 1. Authentication & Security
- **JWT Token Pair Rotation**: Short-lived Access Token (30 min) and rotating Refresh Token (7 days) with atomic family revocation.
- **Password Security**: Strong hashing via `bcrypt`.
- **Active Status Check**: Blocked or inactive accounts are immediately rejected with `403 Forbidden`.

### 🛡️ 2. Role-Based Access Control (RBAC)
- **System Admin**: Full platform oversight.
- **Workspace Roles**:
  - `OWNER`: Full control over workspace settings, project creation, member invitation, and member deletion.
  - `EDITOR`: Create, edit, and delete projects, tasks, and labels.
  - `VIEWER`: Read-only access to workspace resources.
- **ID Probing Prevention**: Accessing resources outside a user's workspace returns `404 Not Found` rather than leaking resource existence.

### 📋 3. Task & Project Management
- **Hierarchical Scoping**: Workspace ➔ Project ➔ Task ➔ Comments & Labels.
- **Labels (Many-to-Many)**: Color-coded tags attached to tasks with unique name constraints per project.
- **Comments**: Collaborative discussion threads with strict author ownership (only comment author can update/delete).

### 🔍 4. Searching, Filtering, Dynamic Sorting & Pagination
- **Multi-field Filtering**: Filter by status (`TODO`, `IN_PROGRESS`, `IN_REVIEW`, `DONE`), priority (`LOW`, `MEDIUM`, `HIGH`, `URGENT`), assignee, attached label, and due date range (`due_date_from`, `due_date_to`).
- **Logical Priority Sorting**: Priority sorting is evaluated logically (`LOW (1) < MEDIUM (2) < HIGH (3) < URGENT (4)`) via database `case()` mapping rather than alphabetical strings.
- **Deterministic Pagination**: Envelope pagination (`total`, `page`, `page_size`, `total_pages`) with primary-key tie-breaker (`id DESC`).

### ⚡ 5. Caching Layer (Redis + In-Memory Fallback)
- **High Performance**: Read-through cache for workspaces, projects, and task listings.
- **Graceful Degradation**: Automatically falls back to thread-safe `InMemoryFallbackCache` if Redis is offline or unreachable.
- **Event-Driven Invalidation**: Mutations (create, update, delete, label attach/detach, membership removal) automatically purge related cache keys.

### 📬 6. Asynchronous Background Tasks
- Dispatches asynchronous jobs via FastAPI's `BackgroundTasks`:
  - **Welcome Email** on user registration.
  - **Task Assignment Alert** on task creation or assignee update.
  - **Status Change Notification** when a task moves through stages.
  - **Workspace Invitation Email** when adding members.
  - **Task Reminder Dispatcher** (`POST /api/v1/tasks/{id}/remind`).

### ⏱️ 7. Observability & Performance Middleware
- Response timing header `X-Process-Time` attached to all HTTP responses.
- Structured request access logging recording method, path, HTTP status, and execution duration.

---

## 🛠 Tech Stack

| Component | Technology | Version | Purpose |
| :--- | :--- | :--- | :--- |
| **Framework** | FastAPI | `>=0.111.0` | Modern, fast web framework |
| **Language** | Python | `3.12+` | Async runtime |
| **ORM** | SQLAlchemy (Asyncio) | `>=2.0.30` | Asynchronous ORM |
| **Migrations** | Alembic | `>=1.13.0` | Database schema migrations |
| **Validation** | Pydantic v2 | `>=2.8.0` | Data parsing and validation |
| **Database** | PostgreSQL / SQLite | `16` / `aiosqlite` | Production & development DB |
| **Cache** | Redis / In-Memory | `7.0` | Distributed caching layer |
| **Testing** | Pytest + pytest-asyncio | `>=8.2.0` | Automated test suite |
| **Linter / Formatter** | Ruff | `>=0.5.0` | PEP8 linting and formatting |
| **Type Checker** | Mypy | `>=1.10.0` | Static type checking |
| **Container** | Docker & Compose | Multi-stage | Production containerization |

---

## 📁 Project Structure

```
fastapi-task-management/
├── alembic/                      # Database migration scripts
│   ├── env.py                    # Alembic async migration environment
│   └── versions/                 # Versioned migration revisions
├── app/
│   ├── api/                      # Routing and dependencies
│   │   ├── deps.py               # Dependency injection & query filters
│   │   └── v1/                   # API v1 routes (auth, users, workspaces, tasks...)
│   ├── core/                     # Application configurations & utilities
│   │   ├── cache.py              # Unified Redis & In-Memory cache service
│   │   ├── config.py             # Pydantic BaseSettings
│   │   ├── constants.py          # Centralized error messages & constants
│   │   ├── exceptions.py         # Custom domain exceptions
│   │   ├── lifespan.py           # Application lifespan manager (startup/shutdown)
│   │   └── security.py           # Password hashing & JWT operations
│   ├── db/                       # Database session & Base model
│   ├── models/                   # SQLAlchemy declarative entities
│   ├── repositories/             # Data access repository layer
│   ├── schemas/                  # Pydantic request/response schemas
│   ├── services/                 # Business logic & domain services
│   │   ├── notification_service.py # Background task dispatcher
│   │   └── ...                   # Auth, Workspace, Task, Project services
│   └── main.py                   # FastAPI app entrypoint & middlewares
├── tests/                        # Comprehensive automated test suite (61 tests)
├── .dockerignore                 # Docker build ignore patterns
├── .env.example                  # Environment configuration template
├── docker-compose.yml            # Docker Compose multi-service definition
├── docker-entrypoint.sh          # Container startup & migration script
├── Dockerfile                    # Production multi-stage Docker build
├── pyproject.toml                # Project metadata & tool configurations
└── requirements.txt              # Production dependency specifications
```

---

## 🐳 Quick Start: Docker Setup (Recommended)

Run the entire platform (FastAPI + PostgreSQL 16 + Redis 7) with a single command:

```bash
# 1. Clone repository
git clone https://github.com/CallMeHieu04/fastapi-task-management.git
cd fastapi-task-management

# 2. Start services with Docker Compose
docker compose up --build
```

The container automatically:
1. Waits for PostgreSQL and Redis health checks to succeed.
2. Applies all Alembic database migrations via `docker-entrypoint.sh`.
3. Starts the Uvicorn server on `http://localhost:8000`.

To stop the services:
```bash
docker compose down
```

---

## 💻 Local Development Setup

### 1. Prerequisites
- Python `3.12+`
- `uv` (recommended) or standard `pip`

### 2. Environment Setup
```bash
# Create and activate virtual environment
uv venv
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
# On Linux / macOS:
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

### 4. Run Database Migrations
```bash
uv run alembic upgrade head
```

### 5. Start Development Server
```bash
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

---

## ⚙️ Environment Variables

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `PROJECT_NAME` | `str` | `"TaskHub"` | Application title displayed in OpenAPI |
| `API_V1_STR` | `str` | `"/api/v1"` | URL prefix for version 1 API |
| `DEBUG` | `bool` | `True` | Debug mode toggle |
| `DATABASE_URL` | `str` | `sqlite+aiosqlite:///./taskhub.db` | Async database connection string |
| `SECRET_KEY` | `str` | *(min 32 chars)* | Cryptographic secret for signing JWT tokens |
| `ALGORITHM` | `str` | `"HS256"` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `int` | `30` | Access token lifespan in minutes |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `int` | `7` | Refresh token lifespan in days |
| `REDIS_URL` | `str` | `"redis://localhost:6379/0"` | Redis connection URL |
| `CACHE_ENABLED` | `bool` | `True` | Toggle caching layer |
| `CACHE_TTL_SECONDS` | `int` | `120` | Default cache expiration time in seconds |

---

## 📖 API Documentation

Once the application is running, interact with the interactive API docs:

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **OpenAPI Schema**: [http://localhost:8000/api/v1/openapi.json](http://localhost:8000/api/v1/openapi.json)

---

## 🧪 Testing & Quality Assurance

TaskHub maintains a comprehensive test suite with 100% passing tests covering RBAC, authentication, search, filtering, caching, and background tasks.

```bash
# Run all tests (61 test cases)
uv run pytest

# Run linter checks
uv run ruff check app tests

# Check code formatting
uv run ruff format --check app tests

# Run static type checking
uv run mypy app tests

# Verify database migration integrity (0 drift)
uv run alembic check
```

---

## 📄 License
This project is licensed under the MIT License.
