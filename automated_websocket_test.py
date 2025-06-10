#!/usr/bin/env python3
"""
Automated WebSocket Test for ADK Voice Agent

This script runs an automated end-to-end test of the ADK Voice Agent via WebSockets.
It follows a predefined conversation flow and verifies the agent's responses.
"""

import asyncio
import json
import uuid
import websockets
from datetime import datetime
import argparse

# Default configuration
DEFAULT_WS_URL = "ws://localhost:8081/ws"
DEFAULT_API_KEY = "development-key"
DEFAULT_SESSION_ID = f"e2e_test_{uuid.uuid4().hex[:8]}"

# Test conversation flow - each tuple is (message, expected_substring)
TEST_CONVERSATION = [
    ("Schedule a meeting for tomorrow at 2pm", "received your message"),
    ("It's a team planning session", "received your message"),
    ("Add John and Sarah as attendees", "received your message"),
    ("Make it a 45 minute meeting", "received your message"),
    ("Add a reminder 15 minutes before", "received your message"),
]

class AutomatedTest:
    """Automated WebSocket test for ADK Voice Agent"""
    
    def __init__(self, ws_url, session_id, api_key, is_audio=False):
        """Initialize the automated test
        
        Args:
            ws_url: WebSocket URL base
            session_id: Session ID for the conversation
            api_key: API key for authentication
            is_audio: Whether to use audio mode
        """
        self.ws_url = ws_url
        self.session_id = session_id
        self.api_key = api_key
        self.is_audio = "true" if is_audio else "false"
        self.full_url = f"{ws_url}/{session_id}?is_audio={self.is_audio}&api_key={api_key}"
        self.messages = []
        self.websocket = None
        self.turn_complete = False
        
    async def connect(self):
        """Connect to the WebSocket server"""
        try:
            self.websocket = await websockets.connect(self.full_url)
            print(f"Connected to {self.full_url}")
            print(f"Session ID: {self.session_id}")
            return True
        except Exception as e:
            print(f"Connection error: {e}")
            return False
    
    async def send_message(self, message):
        """Send a text message to the server
        
        Args:
            message: Text message to send
        """
        if not self.websocket:
            print("Not connected. Please connect first.")
            return
        
        try:
            data = {
                "mime_type": "text/plain",
                "type": "text/plain",
                "data": message,
                "content": message,
                "role": "user"
            }
            await self.websocket.send(json.dumps(data))
            print(f"\n[SENT] {message}")
            self.turn_complete = False
            self.messages.append({"role": "user", "content": message, "timestamp": datetime.now().isoformat()})
        except Exception as e:
            print(f"Error sending message: {e}")
    
    async def receive_messages(self):
        """Receive and display messages from the server"""
        if not self.websocket:
            print("Not connected. Please connect first.")
            return
        
        try:
            full_response = ""
            
            while True:
                try:
                    response = await self.websocket.recv()
                    response_json = json.loads(response)
                    
                    # Check for turn completion
                    if "turn_complete" in response_json and response_json["turn_complete"]:
                        print("[TURN COMPLETE]")
                        self.turn_complete = True
                        break
                    
                    # Process content messages
                    if "content" in response_json and "role" in response_json and response_json["role"] == "model":
                        content = response_json.get("content", "")
                        if content:
                            print(f"[RECEIVED] {content[:100]}..." if len(content) > 100 else f"[RECEIVED] {content}")
                            full_response += content
                            
                except Exception as e:
                    print(f"Error receiving message: {e}")
                    break
            
            if full_response:
                self.messages.append({"role": "model", "content": full_response, "timestamp": datetime.now().isoformat()})
            
            return full_response
        except Exception as e:
            print(f"Error in receive loop: {e}")
    
    async def verify_response(self, response, expected_substring):
        """Verify that the response contains the expected substring
        
        Args:
            response: The response to verify
            expected_substring: The substring to look for
            
        Returns:
            True if the response contains the expected substring, False otherwise
        """
        if not response:
            print(f"[FAIL] No response received, expected: {expected_substring}")
            return False
        
        if expected_substring.lower() in response.lower():
            print(f"[PASS] Response contains expected substring: {expected_substring}")
            return True
        else:
            print(f"[FAIL] Response does not contain expected substring: {expected_substring}")
            print(f"Actual response: {response[:100]}..." if len(response) > 100 else f"Actual response: {response}")
            return False
    
    async def close(self):
        """Close the WebSocket connection"""
        if self.websocket:
            await self.websocket.close()
            print("Connection closed.")
    
    async def run_test(self):
        """Run the automated test"""
        # Connect to the server
        connected = await self.connect()
        if not connected:
            return False
        
        # Receive welcome message
        print("\nWaiting for welcome message...")
        welcome = await self.receive_messages()
        if not welcome:
            print("[FAIL] No welcome message received")
            await self.close()
            return False
        
        print("\n===== RUNNING AUTOMATED WEBSOCKET TEST =====")
        
        # Track test success
        all_tests_passed = True
        
        # Run through the test conversation
        for i, (message, expected_substring) in enumerate(TEST_CONVERSATION):
            print(f"\n--- Turn {i+1}: '{message}' ---")
            
            # Send the message
            await self.send_message(message)
            
            # Receive the response
            print("Waiting for response...")
            response = await self.receive_messages()
            
            # Verify the response
            if not await self.verify_response(response, expected_substring):
                all_tests_passed = False
        
        # Report overall test result
        print("\n===== TEST SUMMARY =====")
        if all_tests_passed:
            print("✅ All tests passed successfully!")
        else:
            print("❌ Some tests failed. Check the logs above for details.")
        
        # Close the connection
        await self.close()
        
        return all_tests_passed


async def main():
    """Main function for the automated test"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Automated WebSocket Test for ADK Voice Agent")
    parser.add_argument("--url", default=DEFAULT_WS_URL, help="WebSocket URL base")
    parser.add_argument("--session", default=DEFAULT_SESSION_ID, help="Session ID for the conversation")
    parser.add_argument("--key", default=DEFAULT_API_KEY, help="API key for authentication")
    parser.add_argument("--audio", action="store_true", help="Use audio mode")
    args = parser.parse_args()
    
    # Create and run the automated test
    test = AutomatedTest(args.url, args.session, args.key, args.audio)
    success = await test.run_test()
    
    # Validate memory persistence
    print("\n===== TESTING MEMORY PERSISTENCE =====")
    try:
        import sys
        import os
        # Add the project root to the path to ensure we can import app modules
        sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
        
        try:
            from app.memory_init import MEMORY, get_memory_type
            memory_type = get_memory_type()
            print(f"Using {memory_type} memory storage")
            
            # Get the conversation history
            history = MEMORY.get_conversation_history(args.session)
            if history:
                print(f"Found {len(history)} messages in conversation history")
                print("Recent messages:")
                for msg in history[-3:]:  # Show last 3 messages
                    print(f"  - [{msg['role']}]: {msg['content'][:50]}..." if len(msg['content']) > 50 else f"  - [{msg['role']}]: {msg['content']}")
                print("✅ Memory persistence test passed!")
            else:
                print("❌ No conversation history found. Memory persistence test failed.")
        except ImportError:
            print("❌ Could not import memory module. Memory persistence test failed.")
    except Exception as e:
        print(f"❌ Error testing memory persistence: {e}")
    
    return success


if __name__ == "__main__":
    print(f"Starting automated WebSocket test at {datetime.now().isoformat()}")
    try:
        success = asyncio.run(main())
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nAutomated test terminated by user.")
        exit(1)
    except Exception as e:
        print(f"Error in main loop: {e}")
        exit(1)
