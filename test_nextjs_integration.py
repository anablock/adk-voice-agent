"""
Next.js Integration Test Tool for ADK Voice Agent

This script simulates the exact WebSocket connection pattern used by the Next.js frontend
to connect to the FastAPI backend. It helps identify and debug integration issues.
"""

import asyncio
import json
import uuid
import websockets
import logging
import sys
import base64
import argparse
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger('nextjs-integration-test')

# Parse command line arguments
parser = argparse.ArgumentParser(description='Test Next.js integration with FastAPI backend')
parser.add_argument('--api-url', default='http://localhost:8081', help='Base API URL')
parser.add_argument('--ws-url', default='ws://localhost:8081/ws', help='WebSocket URL')
parser.add_argument('--api-key', default='development-key', help='API Key')
parser.add_argument('--mode', choices=['text', 'audio'], default='text', help='Test mode (text or audio)')
parser.add_argument('--message', default='What events do I have today?', help='Test message to send')
args = parser.parse_args()

async def test_nextjs_integration():
    # Create a session ID exactly like the frontend does
    session_id = uuid.uuid4().hex[:8]
    logger.info(f"Test session ID: {session_id}")
    
    # Determine audio mode (matches frontend logic)
    is_audio = args.mode == 'audio'
    audio_mode_param = 'true' if is_audio else 'false'
    
    # Construct query parameters (matches frontend logic)
    query_params = f"is_audio={audio_mode_param}&api_key={args.api_key}"
    
    # Construct WebSocket URL exactly as the frontend does
    ws_url = f"{args.ws_url}/{session_id}?{query_params}"
    logger.info(f"Connecting to: {ws_url}")
    
    try:
        async with websockets.connect(ws_url) as websocket:
            logger.info("WebSocket connection established!")
            
            # Send initial ping message (matches frontend)
            ping_message = {
                "type": "ping",
                "api_key": args.api_key
            }
            logger.info(f"Sending ping: {json.dumps(ping_message)}")
            await websocket.send(json.dumps(ping_message))
            
            # Wait for welcome message
            try:
                welcome_message = await asyncio.wait_for(websocket.recv(), timeout=5)
                logger.info(f"Received: {welcome_message}")
            except asyncio.TimeoutError:
                logger.warning("Timeout waiting for welcome message")
            
            # Send a test message (format exactly matches frontend)
            if is_audio:
                # For audio mode, we'd need to send audio chunks
                # This is a simplified version that just sends a text message
                test_message = {
                    "mime_type": "text/plain",
                    "data": args.message,
                    "role": "user"
                }
            else:
                # For text mode, send a text message
                test_message = {
                    "mime_type": "text/plain",
                    "data": args.message,
                    "role": "user"
                }
            
            logger.info(f"Sending message: {json.dumps(test_message)}")
            await websocket.send(json.dumps(test_message))
            
            # If in audio mode, send end-of-audio signal
            if is_audio:
                end_audio_message = {
                    "mime_type": "text/plain",
                    "data": "END_OF_AUDIO",
                    "end_of_audio": True,
                    "role": "user"
                }
                logger.info(f"Sending end of audio: {json.dumps(end_audio_message)}")
                await websocket.send(json.dumps(end_audio_message))
            
            # Listen for responses
            full_response = ""
            message_count = 0
            response_timeout = 15  # Longer timeout for messages
            
            while True:
                try:
                    logger.info(f"Waiting for message #{message_count+1}...")
                    response = await asyncio.wait_for(websocket.recv(), timeout=response_timeout)
                    message_count += 1
                    logger.info(f"Received message #{message_count}: {response}")
                    
                    # Parse JSON response if possible
                    try:
                        json_data = json.loads(response)
                        
                        # Extract content if available
                        if "content" in json_data:
                            logger.info(f"Found content in message: {json_data['content']}")
                            full_response += json_data["content"]
                        elif "data" in json_data and isinstance(json_data["data"], str):
                            logger.info(f"Found data in message: {json_data['data']}")
                            full_response += json_data["data"]
                        
                        # Check for turn completion
                        if json_data.get("turn_complete"):
                            logger.info("Turn complete received, conversation ended")
                            # Continue waiting for additional messages for 1 more second
                            response_timeout = 1
                            continue
                    except json.JSONDecodeError:
                        logger.error(f"Could not parse as JSON: {response}")
                    
                    # Break after receiving turn_complete and at least one content message
                    if message_count > 1 and any(x in full_response for x in ["event", "calendar", "schedule"]):
                        logger.info("Received sufficient response content, ending conversation")
                        break
                        
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout waiting for response after {response_timeout} seconds")
                    break
            
            logger.info(f"Full response: {full_response}")
            
    except websockets.exceptions.InvalidStatusCode as e:
        logger.error(f"Invalid status code: {e}")
        logger.error("This usually indicates a problem with authentication or CORS")
    
    except websockets.exceptions.ConnectionClosedError as e:
        logger.error(f"Connection closed unexpectedly: {e}")
    
    except Exception as e:
        logger.error(f"WebSocket connection error: {type(e).__name__}: {e}")
    
    logger.info("Integration test complete")
    
    # Print summary
    logger.info("\n===== INTEGRATION TEST SUMMARY =====")
    logger.info(f"API URL: {args.api_url}")
    logger.info(f"WebSocket URL: {args.ws_url}")
    logger.info(f"Session ID: {session_id}")
    logger.info(f"Audio Mode: {is_audio}")
    logger.info(f"Message: {args.message}")
    logger.info(f"Response received: {'Yes' if full_response else 'No'}")
    logger.info("===================================\n")
    
    # Print recommendations
    logger.info("RECOMMENDATIONS:")
    logger.info("1. Ensure the Next.js .env.local file has these variables:")
    logger.info("   VOICE_ASSISTANT_API_URL=http://localhost:8081")
    logger.info("   VOICE_ASSISTANT_WS_URL=ws://localhost:8081/ws")
    logger.info("   VOICE_ASSISTANT_API_KEY=development-key")
    logger.info("2. Ensure the FastAPI backend is running on port 8081")
    logger.info("3. Check browser console for any CORS or WebSocket errors")
    logger.info("4. Verify that the WebSocket URL format matches in both frontend and backend")

if __name__ == "__main__":
    logger.info(f"Starting Next.js integration test at {datetime.now()}")
    asyncio.run(test_nextjs_integration())
