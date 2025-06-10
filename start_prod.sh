#!/bin/bash
# Production startup script for ADK Voice Agent with Calendar Integration

# Load environment variables if .env exists
if [ -f .env ]; then
    set -a
    source .env
    set +a
    echo "Loaded environment variables from .env"
else
    echo "Warning: .env file not found. Make sure environment variables are set."
fi

# Set default port if not specified
PORT=${PORT:-8081}
HOST=${HOST:-0.0.0.0}
WORKERS=${WORKERS:-4}
LOG_LEVEL=${LOG_LEVEL:-info}

echo "Starting ADK Voice Agent in production mode on $HOST:$PORT with $WORKERS workers"

# Create data directory if it doesn't exist
mkdir -p data

# Ensure proper Google Calendar credentials
if [ -z "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
    # Check if credentials.json exists in the current directory
    if [ -f "$(pwd)/credentials.json" ]; then
        export GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/credentials.json"
        echo "Using credentials.json from current directory: $GOOGLE_APPLICATION_CREDENTIALS"
    else
        echo "Warning: GOOGLE_APPLICATION_CREDENTIALS not set and no credentials.json found."
        echo "Calendar functionality may be limited."
    fi
fi

# Start with Gunicorn and Uvicorn workers for production
exec gunicorn app.prod_server:app \
    --workers $WORKERS \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind $HOST:$PORT \
    --log-level $LOG_LEVEL \
    --access-logfile - \
    --error-logfile - \
    --timeout 120
