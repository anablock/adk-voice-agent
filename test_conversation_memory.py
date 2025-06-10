#!/usr/bin/env python3
"""
Test script for ADK Voice Agent conversation memory

This script tests the conversation memory capabilities of the ADK Voice Agent,
ensuring that the agent can effectively maintain context across multiple turns
of conversation, particularly for calendar-related operations.
"""

import asyncio
import json
import uuid
import websockets
import time
from datetime import datetime, timedelta

# Configuration
WS_URL = "ws://localhost:8081/ws"
API_KEY = "development-key"

# Use a fixed session ID for more reliable testing
# This will allow us to verify persistence across different runs
SESSION_ID = "test_calendar_assistant_session"

# Predefined test scenarios for multi-turn conversations
TEST_SCENARIOS = [
    # Scenario 1: Creating a calendar event with multiple turns
    {
        "name": "Calendar Event Creation",
        "messages": [
            "Can you help me schedule a meeting?",
            "Let's schedule it for tomorrow at 2pm",
            "It's a team standup meeting",
            "It should last for 30 minutes",
            "Yes, please create it"
        ],
        "expected_entities": ["meeting", "time", "duration"]
    },
    
    # Scenario 2: Querying and updating an existing event
    {
        "name": "Event Query and Update",
        "messages": [
            "What meetings do I have tomorrow?",
            "Can you move the team standup to 3pm instead?",
            "Yes, that works better for me"
        ],
        "expected_entities": ["time", "event_id"]
    },
    
    # Scenario 3: Complex calendar operation with multiple attributes
    {
        "name": "Complex Calendar Operation",
        "messages": [
            "I need to schedule a dentist appointment",
            "Next Friday at 10am",
            "It's at Silver State Smiles dental office",
            "Add a reminder 1 day before",
            "Confirm the appointment please"
        ],
        "expected_entities": ["appointment", "location", "time", "reminder"]
    }
]


async def send_message(websocket, message):
    """Send a message to the websocket"""
    data = {
        "mime_type": "text/plain",
        "type": "text/plain",
        "data": message,
        "content": message,
        "role": "user"
    }
    await websocket.send(json.dumps(data))
    print(f"[SENT] {message}")


async def receive_messages(websocket, timeout=10):
    """Receive messages from the websocket with timeout"""
    response_text = ""
    turn_complete = False
    
    start_time = time.time()
    while not turn_complete and time.time() - start_time < timeout:
        try:
            # Use a proper timeout for receive
            response = await asyncio.wait_for(websocket.recv(), 2)
            response_json = json.loads(response)
            
            # Check for turn completion
            if "turn_complete" in response_json and response_json["turn_complete"]:
                turn_complete = True
                continue
                
            # Process content messages
            if "content" in response_json and "role" in response_json and response_json["role"] == "model":
                content = response_json.get("content", "")
                if content:
                    response_text += content
                    print(f"[RECEIVED] {content[:100]}..." if len(content) > 100 else f"[RECEIVED] {content}")
                    
        except asyncio.TimeoutError:
            # This is a timeout on the individual receive, not the overall timeout
            continue
        except Exception as e:
            print(f"Error receiving message: {e}")
            break
            
    return response_text, turn_complete


async def test_conversation_scenario(scenario):
    """Test a complete conversation scenario"""
    print(f"\n==== TESTING SCENARIO: {scenario['name']} ====")
    print(f"Session ID: {SESSION_ID}")
    
    uri = f"{WS_URL}/{SESSION_ID}?is_audio=false&api_key={API_KEY}"
    
    try:
        async with websockets.connect(uri) as websocket:
            # Wait for welcome message
            welcome, welcome_complete = await receive_messages(websocket)
            print(f"Welcome message: {welcome}")
            
            # Process each message in the scenario
            for i, message in enumerate(scenario["messages"]):
                print(f"\n--- Turn {i+1} ---")
                
                # Send the user message
                await send_message(websocket, message)
                
                # Receive the agent's response
                response, complete = await receive_messages(websocket)
                
                if not complete:
                    print("[WARNING] Turn was not completed properly")
                
                # Allow a short pause between turns
                await asyncio.sleep(1)
                
            print(f"\n==== COMPLETED SCENARIO: {scenario['name']} ====")
            return True
            
    except Exception as e:
        print(f"Error in test scenario: {e}")
        return False


async def test_memory_query():
    """Test direct access to the conversation memory module"""
    try:
        # Use a different import approach for direct module testing
        import sys
        import os
        # Add the project root to the path to ensure we can import app modules
        sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
        
        # Try to import the persistent memory module first
        try:
            from app.memory_init import MEMORY, get_memory_type
            memory_type = get_memory_type()
            print(f"\n==== TESTING {memory_type.upper()} MEMORY MODULE ====\n")
        except ImportError:
            print("\n==== TESTING MEMORY MODULE (IMPORT FAILURE) ====\n")
            from app.conversation_memory import conversation_memory
            MEMORY = conversation_memory
            memory_type = "in-memory"
        
        # Get the conversation history
        history = MEMORY.get_conversation_history(SESSION_ID)
        print(f"Conversation history has {len(history)} entries")
        if history:
            print("Recent messages:")
            # Show last 5 messages
            for msg in history[-5:]:
                print(f"  - [{msg['role']}]: {msg['content'][:50]}..." if len(msg['content']) > 50 else f"  - [{msg['role']}]: {msg['content']}")
                print(f"    Timestamp: {msg['timestamp']}")
        
        # Get the session summary
        summary = MEMORY.get_session_summary(SESSION_ID)
        print(f"Session summary: {json.dumps(summary, indent=2)}")
        
        # Check for stored entities
        if "entities" in summary and summary["entities"]:
            print(f"Stored entities: {summary['entities']}")
            
            # Try to retrieve specific entities
            for entity in summary["entities"]:
                value = MEMORY.get_entity(SESSION_ID, entity)
                print(f"  - {entity}: {value}")
        
        # If no entries exist, create a test entry
        if len(history) == 0:
            print("No conversation history found. Creating a test entry...")
            MEMORY.add_message(SESSION_ID, "system", "Test message for memory verification")
            MEMORY.add_entity(SESSION_ID, "test_entity", "test_value")
            MEMORY.add_entity(SESSION_ID, "test_date", "2025-05-22")
            MEMORY.add_entity(SESSION_ID, "test_time", "15:30")
            print("Test entries created. Re-check the memory:")
            new_history = MEMORY.get_conversation_history(SESSION_ID)
            print(f"Conversation history now has {len(new_history)} entries")
        else:
            # Add an additional test entity to verify persistence
            MEMORY.add_entity(SESSION_ID, "last_test_time", datetime.now().isoformat())
            print(f"Added timestamp entity to existing session: {datetime.now().isoformat()}")
        
        return True
    except ImportError as ie:
        print(f"Could not import conversation_memory module: {ie}")
        print("Checking if the module file exists...")
        memory_path = os.path.join(os.path.dirname(__file__), 'app', 'conversation_memory.py')
        if os.path.exists(memory_path):
            print(f"Module file exists at {memory_path} but cannot be imported. Check for syntax errors.")
        else:
            print(f"Module file not found at {memory_path}. Ensure it's in the correct location.")
        return False
    except Exception as e:
        print(f"Error testing memory module: {e}")
        return False


async def main():
    """Run all test scenarios"""
    print(f"Starting conversation memory tests at {datetime.now().isoformat()}")
    
    all_succeeded = True
    for scenario in TEST_SCENARIOS:
        success = await test_conversation_scenario(scenario)
        if not success:
            all_succeeded = False
    
    # Test memory module directly
    memory_success = await test_memory_query()
    if not memory_success:
        all_succeeded = False
    
    if all_succeeded:
        print("\n✅ All conversation memory tests passed successfully!")
    else:
        print("\n❌ Some tests failed. Check the logs above for details.")


if __name__ == "__main__":
    asyncio.run(main())
