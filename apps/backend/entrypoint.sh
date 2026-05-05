#!/bin/sh
set -e

echo "[entrypoint] Waiting for database..."
until python -c "
import os, sys
import psycopg2
try:
    psycopg2.connect(os.environ['DATABASE_URL']).close()
    sys.exit(0)
except Exception as e:
    print(e)
    sys.exit(1)
" 2>/dev/null; do
    sleep 2
done
echo "[entrypoint] Database ready."

echo "[entrypoint] Running migrations..."
alembic upgrade head
echo "[entrypoint] Migrations done."

echo "[entrypoint] Starting application..."
exec "$@"
