FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn uvicorn

# Copy the rest of the application
COPY . .

# Set environment variables
ENV PORT=8081
ENV HOST=0.0.0.0
ENV PYTHONUNBUFFERED=1

# Create directories for credentials and memory storage
RUN mkdir -p /secrets /app/data

# Make the startup script executable
RUN chmod +x /app/start_prod.sh

# Set volume mounts for persistent data
VOLUME ["/secrets", "/app/data"]

# Expose the port
EXPOSE ${PORT}

# Create necessary directories
RUN mkdir -p /app/data

# Run the application using the production script
CMD ["/app/start_prod.sh"]
