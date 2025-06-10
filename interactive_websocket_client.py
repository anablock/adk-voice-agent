#!/usr/bin/env python3
"""
Interactive WebSocket Client for ADK Voice Agent

This script provides an interactive terminal interface to test the ADK Voice Agent
via WebSockets. It allows sending text messages and receiving responses from the agent.
"""

import asyncio
import json
import sys
import uuid
import websockets
from datetime import datetime
import argparse

# Default configuration
DEFAULT_WS_URL = "ws://localhost:8081/ws"
DEFAULT_API_KEY = "development-key"
DEFAULT_SESSION_ID = f"interactive_{uuid.uuid4().hex[:8]}"

class InteractiveClient:
    """Interactive WebSocket client for ADK Voice Agent"""
    
    def __init__(self, ws_url, session_id, api_key, is_audio=False):
        """Initialize the interactive client
        
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
                            print(f"[RECEIVED] {content}")
                            full_response += content
                            
                except Exception as e:
                    print(f"Error receiving message: {e}")
                    break
            
            if full_response:
                self.messages.append({"role": "model", "content": full_response, "timestamp": datetime.now().isoformat()})
            
            return full_response
        except Exception as e:
            print(f"Error in receive loop: {e}")
    
    async def show_history(self):
        """Display the conversation history"""
        print("\n===== CONVERSATION HISTORY =====")
        for i, msg in enumerate(self.messages):
            print(f"{i+1}. [{msg['role']}]: {msg['content'][:100]}..." if len(msg['content']) > 100 else f"{i+1}. [{msg['role']}]: {msg['content']}")
        print("===============================\n")
    
    async def close(self):
        """Close the WebSocket connection"""
        if self.websocket:
            await self.websocket.close()
            print("Connection closed.")
    
    async def interactive_session(self):
        """Run an interactive session with the agent"""
        # Connect to the server
        connected = await self.connect()
        if not connected:
            return
        
        # Receive welcome message
        print("\nWaiting for welcome message...")
        welcome = await self.receive_messages()
        
        # Enter the interactive loop
        print("\n===== INTERACTIVE VOICE AGENT SESSION =====")
        print("Type your messages and press Enter to send.")
        print("Type '/help' to see available commands.")
        print("Type '/exit' to end the session.")
        print("============================================\n")
        
        while True:
            # Get user input
            user_input = input("You: ").strip()
            
            # Handle commands
            if user_input.lower() == '/exit':
                break
            elif user_input.lower() == '/help':
                print("\nAvailable commands:")
                print("  /exit - End the session")
                print("  /help - Show this help message")
                print("  /history - Show conversation history")
                print("  /clear - Clear the terminal")
                print("  /session - Show current session info")
                continue
            elif user_input.lower() == '/history':
                await self.show_history()
                continue
            elif user_input.lower() == '/clear':
                print("\033c", end="")  # Clear terminal
                continue
            elif user_input.lower() == '/session':
                print(f"\nSession ID: {self.session_id}")
                print(f"WebSocket URL: {self.full_url}")
                print(f"Audio mode: {self.is_audio}")
                print(f"Message count: {len(self.messages)}")
                continue
            elif not user_input:
                continue
            
            # Send the message
            await self.send_message(user_input)
            
            # Receive the response
            print("Waiting for response...")
            await self.receive_messages()
            print()  # Empty line for better readability
        
        # Close the connection
        await self.close()


async def main():
    """Main function for the interactive client"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Interactive WebSocket Client for ADK Voice Agent")
    parser.add_argument("--url", default=DEFAULT_WS_URL, help="WebSocket URL base")
    parser.add_argument("--session", default=DEFAULT_SESSION_ID, help="Session ID for the conversation")
    parser.add_argument("--key", default=DEFAULT_API_KEY, help="API key for authentication")
    parser.add_argument("--audio", action="store_true", help="Use audio mode")
    args = parser.parse_args()
    
    # Create and run the interactive client
    client = InteractiveClient(args.url, args.session, args.key, args.audio)
    await client.interactive_session()


if __name__ == "__main__":
    print(f"Starting interactive WebSocket client at {datetime.now().isoformat()}")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInteractive session terminated by user.")
    except Exception as e:
        print(f"Error in main loop: {e}")
    finally:
        print("Interactive client closed.")
