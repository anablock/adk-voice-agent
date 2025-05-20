#!/usr/bin/env python
import asyncio
import json
import websockets
import uuid
import time

# Configuration - simulating the Next.js application's behavior
WS_URI = "ws://localhost:8081/ws/{session_id}?is_audio={is_audio}&api_key=development-key"
SESSION_ID = "nextjs-test-" + str(uuid.uuid4())[:6]  # Generate a session ID similar to Next.js

async def test_text_connection():
    """Test text-based WebSocket connection"""
    uri = WS_URI.format(session_id=SESSION_ID, is_audio="false")
    print(f"\n=== Testing text connection to: {uri} ===")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✓ Text connection established!")
            
            # First send authentication message (like Next.js does)
            auth_message = {"type": "auth", "api_key": "development-key"}
            print(f"Sending auth message: {json.dumps(auth_message)}")
            await websocket.send(json.dumps(auth_message))
            
            # Wait for welcome messages
            print("Waiting for initial messages...")
            for _ in range(3):
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    print(f"✓ Received: {response[:100]}...")
                except asyncio.TimeoutError:
                    break
            
            # Send a text query with content format (like Next.js)
            next_message = {
                "content": "What meetings do I have today?",
                "role": "user"
            }
            print(f"Sending Next.js style message: {json.dumps(next_message)}")
            await websocket.send(json.dumps(next_message))
            
            # Wait for responses
            print("Waiting for responses...")
            response_count = 0
            for _ in range(4):
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    print(f"✓ Received response {response_count}: {response[:100]}...")
                    response_count += 1
                except asyncio.TimeoutError:
                    break
            
            # Send a text message with mime_type format (alternative format)
            mime_message = {
                "mime_type": "text/plain",
                "data": "Can you schedule a meeting for tomorrow?",
                "role": "user"
            }
            print(f"Sending mime_type style message: {json.dumps(mime_message)}")
            await websocket.send(json.dumps(mime_message))
            
            # Wait for responses
            print("Waiting for more responses...")
            for _ in range(4):
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    print(f"✓ Received response: {response[:100]}...")
                except asyncio.TimeoutError:
                    break
                
    except Exception as e:
        print(f"❌ Error in text connection: {e}")
    
    print("=== Text connection test complete ===")

async def test_audio_connection():
    """Test audio-based WebSocket connection"""
    uri = WS_URI.format(session_id=SESSION_ID, is_audio="true")
    print(f"\n=== Testing audio connection to: {uri} ===")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✓ Audio connection established!")
            
            # First send authentication message
            auth_message = {"type": "auth", "api_key": "development-key"}
            print(f"Sending auth message: {json.dumps(auth_message)}")
            await websocket.send(json.dumps(auth_message))
            
            # Wait for welcome messages
            print("Waiting for initial messages...")
            for _ in range(3):
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    print(f"✓ Received: {response[:100]}...")
                except asyncio.TimeoutError:
                    break
            
            # Send a simulated audio message
            print("Sending simulated audio message")
            # Just send empty base64 data for testing purposes
            await websocket.send(json.dumps({
                "mime_type": "audio/pcm", 
                "data": "c2ltdWxhdGVkIGF1ZGlvIGRhdGE=",  # "simulated audio data" in base64
                "role": "user"
            }))
            
            # Wait for responses
            print("Waiting for responses...")
            for _ in range(4):
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    print(f"✓ Received response: {response[:100]}...")
                except asyncio.TimeoutError:
                    break
                
    except Exception as e:
        print(f"❌ Error in audio connection: {e}")
    
    print("=== Audio connection test complete ===")

async def main():
    print(f"Starting Next.js simulation tests with session ID: {SESSION_ID}")
    await test_text_connection()
    await test_audio_connection()
    print("\nAll tests complete!")

if __name__ == "__main__":
    asyncio.run(main())
