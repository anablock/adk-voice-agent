"""
Production ADK Voice Agent Server with Google Calendar Integration

This module combines the stability of fixed_adk_server.py with the 
calendar integration capabilities from main_audio_config_fix.py.
"""

import os
import sys
import time
import json
import uuid
import base64
import asyncio
from typing import Dict, List, Optional, Any
from pathlib import Path

# Import from fixed_adk_server.py for server stability
from app.fixed_adk_server import (
    app, 
    websocket_endpoint as base_websocket_endpoint,
    api_key_header,
    verify_api_key,
    send_error_message
)

# Import calendar integration
from app.calendar_integration import calendar_manager

# Import conversation memory
try:
    from app.conversation_memory import ConversationMemory
    HAS_MEMORY = True
except ImportError:
    print("Warning: Conversation memory module not available")
    HAS_MEMORY = False

# Set up credentials
credentials_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'credentials.json')
if os.path.exists(credentials_path):
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
    print(f"Set GOOGLE_APPLICATION_CREDENTIALS to: {credentials_path}")

# Create memory manager if available
memory_manager = ConversationMemory() if HAS_MEMORY else None

# Override the websocket endpoint to add calendar integration
@app.websocket("/ws/{session_id}")
async def enhanced_websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    is_audio: str = Query("false"),
    api_key: Optional[str] = Query(None),
    x_api_key: Optional[str] = Header(None),
):
    """Enhanced WebSocket endpoint with calendar integration"""
    # Initialize memory for this session if available
    if memory_manager:
        memory_manager.initialize_session(session_id)
    
    # Connect to the WebSocket
    await websocket.accept()
    
    # Standard API key verification
    try:
        verify_api_key(api_key or x_api_key)
    except HTTPException as e:
        await send_error_message(websocket, f"Authentication error: {e.detail}")
        await websocket.close()
        return
    
    # Process is_audio parameter
    is_audio_mode = is_audio.lower() == "true"
    
    try:
        # Send welcome message
        welcome_message = "Welcome to the ADK Voice Agent with Google Calendar integration!"
        if memory_manager:
            # Add any context from previous conversations
            context = memory_manager.get_context(session_id)
            if context:
                welcome_message += f" I remember we were discussing {context}."
        
        await websocket.send_json({
            "type": "message",
            "content": welcome_message
        })
        
        # Main conversation loop
        while True:
            # Wait for message from client
            message = await websocket.receive_text()
            
            try:
                data = json.loads(message)
                text = data.get("text", "")
                
                # Process the message
                if not text:
                    await send_error_message(websocket, "No text content provided")
                    continue
                
                # Check if this is a calendar-related query
                if any(keyword in text.lower() for keyword in ["calendar", "schedule", "event", "meeting", "appointment"]):
                    try:
                        # Process with calendar integration
                        response = calendar_manager.handle_calendar_query(text, session_id)
                        
                        # Store in memory if available
                        if memory_manager:
                            memory_manager.add_interaction(session_id, text, response)
                        
                        # Send response to client
                        await websocket.send_json({
                            "type": "message",
                            "content": response
                        })
                        
                        # Send turn complete message
                        await websocket.send_json({"type": "turnComplete"})
                        
                    except Exception as e:
                        error_msg = f"I encountered an error processing your calendar request: {str(e)}"
                        await websocket.send_json({
                            "type": "message",
                            "content": error_msg
                        })
                        await websocket.send_json({"type": "turnComplete"})
                
                # If not calendar-related, pass to the regular handler
                else:
                    # Forward to base websocket handler logic
                    # This is simplified as we can't directly call the base handler
                    # In a real implementation, you would refactor the base handler logic
                    # to be callable from here
                    response = f"I understood your message: '{text}'. How can I help you further?"
                    
                    # Store in memory if available
                    if memory_manager:
                        memory_manager.add_interaction(session_id, text, response)
                    
                    # Send response to client
                    await websocket.send_json({
                        "type": "message",
                        "content": response
                    })
                    
                    # Send turn complete message
                    await websocket.send_json({"type": "turnComplete"})
            
            except json.JSONDecodeError:
                await send_error_message(websocket, "Invalid JSON message")
            except Exception as e:
                await send_error_message(websocket, f"Error processing message: {str(e)}")
    
    except WebSocketDisconnect:
        print(f"Client disconnected from session {session_id}")
    except Exception as e:
        print(f"Error in WebSocket connection: {str(e)}")
        try:
            await websocket.close()
        except:
            pass

# Run the server if this script is executed directly
if __name__ == "__main__":
    import uvicorn
    
    # Get port from environment or default to 8081
    port = int(os.environ.get("PORT", 8081))
    host = os.environ.get("HOST", "0.0.0.0")
    
    print(f"Starting Production ADK Voice Agent on {host}:{port}")
    print(f"Calendar integration is {'active' if calendar_manager.initialized else 'inactive'}")
    print(f"Conversation memory is {'active' if HAS_MEMORY else 'inactive'}")
    
    uvicorn.run("app.prod_server:app", host=host, port=port)
