# Use an official Python runtime as a parent image
FROM python:3.11-slim-bullseye

# Set the working directory in the container
WORKDIR /app

# Install pip dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install PostgreSQL client for pg_isready
RUN apt-get update && apt-get install -y postgresql-client && rm -rf /var/lib/apt/lists/*

# Copy the custom entrypoint script and make it executable
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Copy the rest of the current directory contents into the container at /app
COPY . .

# Expose the port that the application will listen on
ENV PORT 8080
EXPOSE ${PORT}

# Set the custom entrypoint script.
ENTRYPOINT ["/app/docker-entrypoint.sh"]


