#!/bin/bash
# Initialize database with Alembic migrations

set -e

echo "Waiting for PostgreSQL to be ready..."
until docker exec postgres pg_isready -U postgres -d deepfishy > /dev/null 2>&1; do
  echo "Waiting for database..."
  sleep 2
done

echo "PostgreSQL is ready!"
echo "Running Alembic migrations..."

# Run migrations inside the server container
docker exec server alembic upgrade head

echo "Database initialized successfully!"

