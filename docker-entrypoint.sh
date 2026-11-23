#!/bin/sh
set -e

echo "=== [TaskHub] Container Entrypoint Starting ==="
echo "=== [TaskHub] Executing database migrations via Alembic ==="
alembic upgrade head
echo "=== [TaskHub] Database migrations applied successfully ==="

echo "=== [TaskHub] Handing over process execution to command ==="
exec "$@"
