#!/usr/bin/env python
import asyncio
import json
import websockets
import uuid

# Configuration
WS_URI = "ws://localhost:8081/ws/{session_id}?is_audio=false&api_key=development-key"
SESSION_ID = str(uuid.uuid4())[:8]  # Generate a random session ID

async def test_websocket():
    """Test WebSocket connection to our FastAPI backend"""
    uri = WS_URI.format(session_id=SESSION_ID)
    print(f"Connecting to: {uri}")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("Connection established!")
            
            # Wait for welcome or authentication messages
            print("Waiting for initial messages...")
            for _ in range(3):  # Try to receive up to 3 initial messages
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    print(f"Received: {response}")
                except asyncio.TimeoutError:
                    print("Timeout waiting for message")
                    break
            
            # Send a text message
            test_message = {
                "mime_type": "text/plain",
                "type": "text/plain",
                "data": "Hello, this is a test message!",
                "content": "Hello, this is a test message!",
                "role": "user"
            }
            print(f"Sending message: {json.dumps(test_message)}")
            await websocket.send(json.dumps(test_message))
            
            # Wait for responses
            print("Waiting for responses...")
            for _ in range(3):  # Try to receive up to 3 responses
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    print(f"Received: {response}")
                except asyncio.TimeoutError:
                    print("Timeout waiting for response")
                    break
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print("Starting WebSocket test...")
    asyncio.run(test_websocket())
    print("Test complete.")
