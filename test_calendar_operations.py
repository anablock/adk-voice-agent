"""
Comprehensive test script for the ADK Voice Agent
Tests all calendar operations: list, create, edit, and delete events
"""

import asyncio
import json
import uuid
import websockets
import logging
import sys
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger('calendar-operations-test')

# WebSocket connection settings
WS_URL = "ws://localhost:8081/ws"
API_KEY = "development-key"

# Calendar operation queries to test
CALENDAR_QUERIES = [
    "What events do I have tomorrow?",
    "What's on my calendar for May 25th?",
    "Can you schedule a meeting with John at 3pm on Friday?",
    "Move my meeting with John to 4pm",
    "Delete my 4pm meeting on Friday"
]

async def test_calendar_operation(query):
    """Test a specific calendar operation query"""
    # Create a session ID
    session_id = uuid.uuid4().hex[:8]
    logger.info(f"\n==== Testing Calendar Query: '{query}' ====")
    logger.info(f"Session ID: {session_id}")
    
    # Construct WebSocket URL
    query_params = f"is_audio=false&api_key={API_KEY}"
    ws_url = f"{WS_URL}/{session_id}?{query_params}"
    logger.info(f"Connecting to: {ws_url}")
    
    try:
        async with websockets.connect(ws_url) as websocket:
            logger.info("WebSocket connection established!")
            
            # Wait for welcome message
            welcome_message = await asyncio.wait_for(websocket.recv(), timeout=5)
            logger.info(f"Received welcome message")
            
            # Skip any turn_complete messages after welcome
            try:
                while True:
                    message = await asyncio.wait_for(websocket.recv(), timeout=1)
                    data = json.loads(message)
                    if not data.get("turn_complete"):
                        break
            except asyncio.TimeoutError:
                pass
            
            # Send the calendar query
            test_message = {
                "mime_type": "text/plain",
                "data": query,
                "role": "user"
            }
            
            logger.info(f"Sending query: '{query}'")
            await websocket.send(json.dumps(test_message))
            
            # Listen for responses
            full_response = ""
            message_count = 0
            
            while True:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=15)
                    message_count += 1
                    
                    # Parse JSON response
                    try:
                        json_data = json.loads(response)
                        
                        # Extract content if available
                        if "content" in json_data:
                            content = json_data["content"]
                            logger.info(f"Response content: '{content}'")
                            full_response += content
                        elif "data" in json_data and isinstance(json_data["data"], str):
                            data = json_data["data"]
                            logger.info(f"Response data: '{data}'")
                            full_response += data
                        
                        # Check for turn completion
                        if json_data.get("turn_complete"):
                            logger.info("Turn complete received, ending conversation")
                            break
                    except json.JSONDecodeError:
                        logger.error(f"Could not parse as JSON: {response}")
                    
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout waiting for response after 15 seconds")
                    break
            
            logger.info(f"Full response to '{query}':\n{full_response}\n")
            return full_response
            
    except Exception as e:
        logger.error(f"Error during test: {type(e).__name__}: {e}")
        return None

async def run_all_tests():
    """Run all calendar operation tests"""
    results = {}
    
    for query in CALENDAR_QUERIES:
        response = await test_calendar_operation(query)
        results[query] = response
        # Add delay between tests
        await asyncio.sleep(2)
    
    logger.info("\n===== CALENDAR OPERATIONS TEST SUMMARY =====")
    for query, response in results.items():
        success = response is not None and len(response) > 0
        logger.info(f"Query: '{query}'")
        logger.info(f"Success: {success}")
        logger.info(f"Response: {response[:100]}..." if response and len(response) > 100 else f"Response: {response}")
        logger.info("-" * 50)

if __name__ == "__main__":
    logger.info(f"Starting calendar operations test at {datetime.now()}")
    asyncio.run(run_all_tests())
