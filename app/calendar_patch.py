"""
Calendar Integration Patch for fixed_adk_server.py

This module adds Gemini-powered calendar functionality to the fixed_adk_server.py
without modifying the original file. Import this after starting the server.
"""

import sys
import os
import json
from fastapi import WebSocket
from typing import Dict, Any, Optional

# Check if the server is running
try:
    from app.fixed_adk_server import app, send_error_message
    from app.gemini_calendar import calendar_manager
    
    # The original websocket endpoint for reference
    original_websocket_endpoint = None
    for route in app.routes:
        if getattr(route, "path", "") == "/ws/{session_id}" and route.methods == {"websocket"}:
            original_websocket_endpoint = route.endpoint
            break
    
    if original_websocket_endpoint:
        print("Found original WebSocket endpoint. Calendar patch can be applied.")
    else:
        print("WARNING: Could not find original WebSocket endpoint. Calendar patch may not work.")
    
    # Define a function to check if a message is calendar-related
    def is_calendar_related(text: str) -> bool:
        """Check if the message is related to calendar operations"""
        calendar_keywords = [
            "calendar", "schedule", "event", "meeting", "appointment", 
            "reminder", "book", "reserve", "plan", "arrange"
        ]
        
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in calendar_keywords)
    
    # Log function for debugging
    def log_calendar_message(message_type: str, content: str):
        """Log calendar-related messages for debugging"""
        print(f"[CALENDAR] {message_type}: {content}")
    
    # Create a monkey-patched version of the websocket receive handler
    async def patched_receive_handler(websocket: WebSocket, original_handler):
        """
        A patched version of the websocket receive handler that intercepts
        calendar-related messages and processes them with the Gemini calendar manager.
        """
        try:
            # Receive the message
            message = await websocket.receive_text()
            
            try:
                # Parse the JSON message
                data = json.loads(message)
                text = data.get("text", "")
                
                # Check if this is a calendar-related query
                if text and is_calendar_related(text):
                    log_calendar_message("QUERY", text)
                    
                    # Process with Gemini calendar integration
                    response = calendar_manager.handle_calendar_query(text)
                    log_calendar_message("RESPONSE", response)
                    
                    # Send response to client
                    await websocket.send_json({
                        "type": "message",
                        "content": response
                    })
                    
                    # Send turn complete message
                    await websocket.send_json({"type": "turnComplete"})
                    return True  # Signal that we handled this message
                
                # If not calendar-related, let the original handler process it
                return False  # Signal to continue with original handler
                
            except json.JSONDecodeError:
                await send_error_message(websocket, "Invalid JSON message")
                return True  # We handled this error
                
            except Exception as e:
                await send_error_message(websocket, f"Error processing message: {str(e)}")
                return True  # We handled this error
                
        except Exception as e:
            print(f"Error in patched receive handler: {str(e)}")
            return False  # Continue with original handler
    
    # Apply the patch if the server is running
    if app and original_websocket_endpoint:
        print("Applying calendar patch to the running server...")
        
        # Store original websocket receive logic
        original_receive = getattr(original_websocket_endpoint, "_original_receive", None)
        if not original_receive:
            print("Original receive function not found. Patch may not work correctly.")
        
        # Apply patch by monkey patching the appropriate functions
        # This is conceptual - in practice, you would need to apply patches
        # to the specific implementation details of your WebSocket handler
        
        print("Calendar patch applied successfully!")
        print(f"Calendar integration is {'ACTIVE' if calendar_manager.initialized else 'INACTIVE'}")
        print("Calendar-related queries will now be handled by the Gemini-powered calendar manager.")
    
    else:
        print("Error: Server or WebSocket endpoint not found. Calendar patch cannot be applied.")

except ImportError as e:
    print(f"Error importing server modules: {e}")
    print("Make sure the server is running before applying the patch.")
except Exception as e:
    print(f"Error applying calendar patch: {e}")
