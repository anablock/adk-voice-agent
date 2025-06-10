"""
Test script for the ADK Voice Agent to test specific calendar queries
"""

import asyncio
import json
import uuid
import websockets
import logging
import sys
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger('calendar-query-test')

# WebSocket connection settings
WS_URL = "ws://localhost:8081/ws"
API_KEY = "development-key"
QUERY = "What is on my calendar tomorrow?"

async def test_calendar_query():
    # Create a session ID
    session_id = uuid.uuid4().hex[:8]
    logger.info(f"Test session ID: {session_id}")
    
    # Construct WebSocket URL
    query_params = f"is_audio=false&api_key={API_KEY}"
    ws_url = f"{WS_URL}/{session_id}?{query_params}"
    logger.info(f"Connecting to: {ws_url}")
    
    try:
        async with websockets.connect(ws_url) as websocket:
            logger.info("WebSocket connection established!")
            
            # Wait for welcome message
            welcome_message = await asyncio.wait_for(websocket.recv(), timeout=5)
            logger.info(f"Received welcome: {welcome_message}")
            
            # Skip any turn_complete messages after welcome
            try:
                while True:
                    message = await asyncio.wait_for(websocket.recv(), timeout=1)
                    logger.info(f"Received: {message}")
                    data = json.loads(message)
                    if not data.get("turn_complete"):
                        break
            except asyncio.TimeoutError:
                pass
            
            # Send the calendar query
            test_message = {
                "mime_type": "text/plain",
                "data": QUERY,
                "role": "user"
            }
            
            logger.info(f"Sending query: {json.dumps(test_message)}")
            await websocket.send(json.dumps(test_message))
            
            # Listen for responses
            full_response = ""
            message_count = 0
            
            while True:
                try:
                    logger.info(f"Waiting for response #{message_count+1}...")
                    response = await asyncio.wait_for(websocket.recv(), timeout=10)
                    message_count += 1
                    logger.info(f"Received response #{message_count}: {response}")
                    
                    # Parse JSON response
                    try:
                        json_data = json.loads(response)
                        
                        # Extract content if available
                        if "content" in json_data:
                            logger.info(f"Found content: {json_data['content']}")
                            full_response += json_data["content"]
                        elif "data" in json_data and isinstance(json_data["data"], str):
                            logger.info(f"Found data: {json_data['data']}")
                            full_response += json_data["data"]
                        
                        # Check for turn completion
                        if json_data.get("turn_complete"):
                            logger.info("Turn complete received, ending conversation")
                            break
                    except json.JSONDecodeError:
                        logger.error(f"Could not parse as JSON: {response}")
                    
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout waiting for response after 10 seconds")
                    break
            
            logger.info(f"Full response to '{QUERY}': {full_response}")
            
    except Exception as e:
        logger.error(f"Error during test: {type(e).__name__}: {e}")
    
    logger.info("Calendar query test complete")

if __name__ == "__main__":
    logger.info(f"Starting calendar query test at {datetime.now()}")
    asyncio.run(test_calendar_query())
