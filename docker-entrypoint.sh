#!/bin/sh

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
until pg_isready -h db -p 5432 -U user; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 1
done
echo "PostgreSQL is up - executing command"

# Initialize the database (only if tables don't exist)
flask init-db

# Start the main application process using Gunicorn
exec gunicorn -b :${PORT} --workers 2 --threads 4 app:app
