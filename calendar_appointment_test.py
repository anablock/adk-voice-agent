#!/usr/bin/env python3
"""
Calendar Appointment Scheduling Test for ADK Voice Agent

This script tests how the voice agent handles appointment scheduling requests.
"""

import asyncio
import json
import websockets
from datetime import datetime

# Configuration
WS_URL = "ws://localhost:8081/ws"
API_KEY = "development-key"
SESSION_ID = "calendar_appointment_test_session"
TEST_QUERY = "schedule appointment for my dentist tomorrow at 3"

async def run_test():
    """Run the calendar appointment scheduling test"""
    # Connect to WebSocket
    full_url = f"{WS_URL}/{SESSION_ID}?is_audio=false&api_key={API_KEY}"
    print(f"Connecting to {full_url}")
    
    async with websockets.connect(full_url) as websocket:
        print(f"Connected! Session ID: {SESSION_ID}")
        
        # Wait for welcome message
        print("\nWaiting for welcome message...")
        welcome_response = ""
        while True:
            response = await websocket.recv()
            response_json = json.loads(response)
            
            if "turn_complete" in response_json and response_json["turn_complete"]:
                break
                
            if "content" in response_json and response_json["role"] == "model":
                content = response_json.get("content", "")
                if content:
                    welcome_response += content
                    print(f"[WELCOME] {content}")
        
        # Send the appointment scheduling request
        print(f"\nSending request: '{TEST_QUERY}'")
        query_data = {
            "mime_type": "text/plain",
            "type": "text/plain",
            "data": TEST_QUERY,
            "content": TEST_QUERY,
            "role": "user"
        }
        await websocket.send(json.dumps(query_data))
        
        # Receive and process the response
        full_response = ""
        print("\nWaiting for response...")
        while True:
            try:
                response = await websocket.recv()
                response_json = json.loads(response)
                
                if "turn_complete" in response_json and response_json["turn_complete"]:
                    print("[TURN COMPLETE]")
                    break
                    
                if "content" in response_json and response_json["role"] == "model":
                    content = response_json.get("content", "")
                    if content:
                        full_response += content
                        print(f"[RESPONSE] {content}")
            except Exception as e:
                print(f"Error receiving message: {e}")
                break
        
        # Analyze the response
        print("\n===== RESPONSE ANALYSIS =====")
        print(f"Full response: {full_response}")
        
        # Check if response contains specific appointment information
        expected_keywords = [
            "tomorrow", "3", "dentist", "appointment", "schedule", "created"
        ]
        
        print("\nChecking for expected keywords:")
        for keyword in expected_keywords:
            if keyword.lower() in full_response.lower():
                print(f"✅ Response contains '{keyword}'")
            else:
                print(f"❌ Response does not contain '{keyword}'")
        
        # Test memory for entity extraction
        print("\n===== MEMORY ANALYSIS =====")
        try:
            import sys
            import os
            sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
            
            try:
                from app.memory_init import MEMORY
                
                # Check for extracted entities
                entities_to_check = [
                    ("date", "tomorrow"),
                    ("time", "3"),
                    ("event_type", "appointment"),
                    ("action", "create")
                ]
                
                for entity_type, expected_value in entities_to_check:
                    entity_value = MEMORY.get_entity(SESSION_ID, entity_type)
                    if entity_value:
                        if expected_value.lower() in str(entity_value).lower():
                            print(f"✅ {entity_type.capitalize()} entity correctly extracted: {entity_value}")
                        else:
                            print(f"❓ {entity_type.capitalize()} entity extracted but with unexpected value: {entity_value}")
                    else:
                        print(f"❌ No {entity_type} entity extracted")
                
                # Check conversation history
                history = MEMORY.get_conversation_history(SESSION_ID)
                print(f"Conversation has {len(history)} messages")
                
            except ImportError:
                print("❌ Could not import memory module")
        except Exception as e:
            print(f"❌ Error analyzing memory: {e}")

if __name__ == "__main__":
    print(f"Starting calendar appointment scheduling test at {datetime.now().isoformat()}")
    asyncio.run(run_test())
    print("Test completed!")
