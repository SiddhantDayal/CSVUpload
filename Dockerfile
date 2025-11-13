# Use an official Python runtime as a parent image
FROM python:3.11-slim-bullseye

# Set the working directory in the container
WORKDIR /app

# Install pip dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install PostgreSQL client for pg_isready
RUN apt-get update && apt-get install -y postgresql-client && rm -rf /var/lib/apt/lists/*

# Copy the current directory contents into the container at /app
COPY . .

# Ensure gunicorn is installed for production web serving
# (Already handled by requirements.txt, but explicit check or install won't hurt)
# RUN pip install gunicorn

# Expose the port that the application will listen on
# Cloud Run expects the application to listen on the port specified by the PORT environment variable
ENV PORT 8080
EXPOSE ${PORT}

# Run the Flask application using Gunicorn
# The default entrypoint for Cloud Run is `gunicorn -b :$PORT app:app`
# `app:app` means the 'app' variable within the 'app.py' file
CMD exec gunicorn -b :${PORT} --workers 2 --threads 4 app:app
