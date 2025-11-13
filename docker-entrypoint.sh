#!/bin/sh

echo "Starting docker-entrypoint.sh script..."

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
until pg_isready -h db -p 5432 -U user; do
  echo "PostgreSQL is unavailable - sleeping (retry in 1s)"
  sleep 1
done
echo "PostgreSQL is up - connection established."

# Initialize the database (only if tables don't exist)
echo "Running Flask DB initialization (flask init-db)..."
flask init-db
echo "Flask DB initialization complete."

# Start the main application process using Gunicorn
echo "Starting Gunicorn server..."
exec gunicorn -b :${PORT} --workers 2 --threads 4 app:app
echo "Gunicorn exited." # This line will likely not be reached due to exec