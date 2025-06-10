#!/bin/bash
# Restart script for ADK Voice Agent

echo "=== ADK Voice Agent Server Restart ==="
echo "Stopping any existing voice agent servers..."
pkill -f "python -m app.main_audio_config_fix" || true
sleep 1

# Make sure port 8081 is free
if lsof -i:8081 > /dev/null; then
    echo "Warning: Port 8081 is still in use. Attempting to free it..."
    lsof -i:8081 -t | xargs kill -9 2>/dev/null || true
    sleep 1
fi

echo "Starting voice agent server with fixed code..."
cd "$(dirname "$0")"
export PYTHONPATH="$(pwd):$PYTHONPATH"
python -m app.main_audio_config_fix > server.log 2>&1 &
server_pid=$!

# Wait a moment for server to start
sleep 2

# Check if server is actually running
if ps -p $server_pid > /dev/null; then
    echo "Server started successfully! Process ID: $server_pid"
    echo "Log file: $(pwd)/server.log"
    # Verify it's listening on the right port
    if lsof -i:8081 -a -p $server_pid > /dev/null; then
        echo "Server is listening on port 8081"
    else
        echo "Warning: Server is running but not listening on port 8081"
        tail -10 server.log
    fi
else
    echo "Error: Server failed to start. Check server.log for details:"
    tail -20 server.log
    exit 1
fi

echo ""
echo "=== Test Commands ==="
echo "To test the conversation memory integration:"
echo "python test_conversation_memory.py"
echo ""
echo "To test the voice integration:"
echo "python test_voice_integration.py"
