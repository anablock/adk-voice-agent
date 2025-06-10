#!/bin/bash
# Test script for production build without disrupting existing services

# Use a different port for testing
export PORT=8082
export HOST=0.0.0.0
export WORKERS=1
export LOG_LEVEL=debug
export GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/credentials.json"

echo "Testing production build on $HOST:$PORT"
echo "Using Google Calendar credentials: $GOOGLE_APPLICATION_CREDENTIALS"

# Run the production server in the background
python app/main_prod.py &
SERVER_PID=$!

echo "Server started with PID: $SERVER_PID"
echo "Waiting for server to initialize..."
sleep 5

# Test the calendar operations
echo "Running calendar operations test against test server..."
PYTHONPATH=$(pwd) TEST_WS_URL="ws://localhost:8082/ws" python -c "
import sys
import os
import asyncio
from test_calendar_operations import run_all_tests

# Override WebSocket URL for testing
os.environ['WS_URL'] = 'ws://localhost:8082/ws'

# Run the tests
asyncio.run(run_all_tests())
"

# Capture the exit code
TEST_EXIT_CODE=$?

# Clean up - kill the server process
echo "Cleaning up - stopping test server..."
kill $SERVER_PID

# Wait for process to terminate
wait $SERVER_PID 2>/dev/null

echo "Test completed with exit code: $TEST_EXIT_CODE"
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo "✅ Production build test PASSED"
else
    echo "❌ Production build test FAILED"
fi

exit $TEST_EXIT_CODE
