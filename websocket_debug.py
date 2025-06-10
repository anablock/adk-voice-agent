"""
WebSocket connection debugger for ADK Voice Agent
"""

import asyncio
import json
import sys
import websockets
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger('websocket-debug')

# Connection parameters
WS_URL = "ws://localhost:8081/ws"
SESSION_ID = "debug_session"
API_KEY = "development-key"

async def debug_websocket():
    # Construct WebSocket URL with parameters
    full_url = f"{WS_URL}/{SESSION_ID}?is_audio=false&api_key={API_KEY}"
    logger.info(f"Connecting to: {full_url}")
    
    try:
        # Attempt connection with detailed error information
        async with websockets.connect(full_url) as websocket:
            logger.info("WebSocket connection established!")
            
            # Listen for initial message (welcome)
            logger.info("Waiting for initial message...")
            try:
                welcome_message = await asyncio.wait_for(websocket.recv(), timeout=5)
                logger.info(f"Received welcome: {welcome_message}")
                
                # Parse JSON if possible
                try:
                    json_data = json.loads(welcome_message)
                    logger.info(f"JSON parsed successfully: {json.dumps(json_data, indent=2)}")
                except json.JSONDecodeError:
                    logger.error(f"Could not parse as JSON: {welcome_message}")
            except asyncio.TimeoutError:
                logger.warning("Timeout waiting for welcome message")
            
            # Send a test message
            test_message = {
                "mime_type": "text/plain",
                "data": "Hello, this is a test message!",
                "role": "user"
            }
            logger.info(f"Sending message: {json.dumps(test_message)}")
            await websocket.send(json.dumps(test_message))
            
            # Listen for responses with a timeout
            while True:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5)
                    logger.info(f"Received response: {response}")
                    
                    # Parse JSON response
                    try:
                        json_data = json.loads(response)
                        if json_data.get("turn_complete"):
                            logger.info("Turn complete received, conversation ended")
                            break
                    except json.JSONDecodeError:
                        logger.error(f"Could not parse as JSON: {response}")
                        
                except asyncio.TimeoutError:
                    logger.warning("Timeout waiting for response")
                    break
    
    except websockets.exceptions.InvalidStatusCode as e:
        logger.error(f"Invalid status code: {e}")
        logger.error(f"This usually indicates a problem with authentication or CORS")
    
    except websockets.exceptions.ConnectionClosedError as e:
        logger.error(f"Connection closed unexpectedly: {e}")
    
    except Exception as e:
        logger.error(f"WebSocket connection error: {type(e).__name__}: {e}")
    
    logger.info("Debug session complete")

if __name__ == "__main__":
    asyncio.run(debug_websocket())
