#!/bin/sh
set -eu

# Docker DNS can take a moment to publish the `db` service name after a
# container is created.  Do not make the whole backend restart on that brief
# startup race; wait for Alembic to establish the database connection.
attempt=1
max_attempts=15
until alembic upgrade head; do
  if [ "$attempt" -ge "$max_attempts" ]; then
    echo "Database is still unavailable after ${max_attempts} attempts." >&2
    exit 1
  fi

  echo "Database not ready (attempt ${attempt}/${max_attempts}); retrying in 2 seconds..." >&2
  attempt=$((attempt + 1))
  sleep 2
done

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
