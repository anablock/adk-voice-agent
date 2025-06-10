#!/usr/bin/env python3
"""
Calendar Query Test for ADK Voice Agent

This script tests how the voice agent responds to a specific calendar query.
"""

import asyncio
import json
import websockets
from datetime import datetime

# Configuration
WS_URL = "ws://localhost:8081/ws"
API_KEY = "development-key"
SESSION_ID = "calendar_query_test_session"
TEST_QUERY = "What is on my calendar tomorrow?"

async def run_test():
    """Run the calendar query test"""
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
        
        # Send the calendar query
        print(f"\nSending query: '{TEST_QUERY}'")
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
        
        # Check if response contains specific calendar information
        if "tomorrow" in full_response.lower():
            print("✅ Response mentions 'tomorrow'")
        else:
            print("❌ Response does not mention 'tomorrow'")
            
        if "meeting" in full_response.lower() or "appointment" in full_response.lower() or "event" in full_response.lower():
            print("✅ Response mentions calendar events (meeting/appointment/event)")
        else:
            print("❌ Response does not mention calendar events")
            
        if "schedule" in full_response.lower() or "calendar" in full_response.lower():
            print("✅ Response mentions schedule/calendar")
        else:
            print("❌ Response does not mention schedule/calendar")
        
        # Test memory for entity extraction
        print("\n===== MEMORY ANALYSIS =====")
        try:
            import sys
            import os
            sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
            
            try:
                from app.memory_init import MEMORY
                
                # Check if "date" entity was extracted
                date_entity = MEMORY.get_entity(SESSION_ID, "date")
                if date_entity:
                    print(f"✅ Date entity extracted: {date_entity}")
                else:
                    print("❌ No date entity extracted")
                    
                # Check conversation history
                history = MEMORY.get_conversation_history(SESSION_ID)
                print(f"Conversation has {len(history)} messages")
                
            except ImportError:
                print("❌ Could not import memory module")
        except Exception as e:
            print(f"❌ Error analyzing memory: {e}")

if __name__ == "__main__":
    print(f"Starting calendar query test at {datetime.now().isoformat()}")
    asyncio.run(run_test())
    print("Test completed!")
