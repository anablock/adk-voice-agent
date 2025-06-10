"""
Standalone WebSocket server for Calendar Assistant integration
This version provides reliable responses without depending on Gemini model availability
"""

import asyncio
import json
import os
import time
import uuid
from typing import Dict, List, Optional, Any

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Load environment variables
load_dotenv()

# Configuration
APP_NAME = "ADK Voice Agent"
API_KEY = os.getenv("API_KEY", "development-key")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

# Store active sessions
active_sessions: Dict[str, Dict[str, Any]] = {}

# Create FastAPI app
app = FastAPI(title="Calendar Assistant API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API status endpoint
@app.get("/api/status")
async def status():
    """API status endpoint for health checks"""
    return JSONResponse({
        "status": "online",
        "has_gemini_key": bool(os.getenv("GOOGLE_API_KEY")),
        "has_calendar_credentials": os.path.exists(os.getenv("GOOGLE_APPLICATION_CREDENTIALS", ""))
    })

# Calendar operation responses (simulated)
CALENDAR_RESPONSES = {
    "today": "I don't see any events scheduled for today.",
    "tomorrow": "You have 2 events tomorrow: 'Team Meeting' at 10:00 AM and 'Lunch with Alex' at 12:30 PM.",
    "this week": "You have 5 events this week, including 'Project Review' on Thursday at 2:00 PM.",
    "create": "I've created the event on your calendar. You're all set!",
    "delete": "I've removed that event from your calendar.",
    "update": "I've updated the event as requested.",
    "default": "I'll help you manage your calendar. What would you like to do?"
}

# Generate appropriate calendar response
def get_calendar_response(query: str) -> str:
    """Generate a calendar response based on the query"""
    query = query.lower()
    
    if "today" in query and ("event" in query or "schedule" in query or "calendar" in query):
        return CALENDAR_RESPONSES["today"]
    elif "tomorrow" in query and ("event" in query or "schedule" in query or "calendar" in query):
        return CALENDAR_RESPONSES["tomorrow"]
    elif ("this week" in query or "upcoming" in query) and ("event" in query or "schedule" in query or "calendar" in query):
        return CALENDAR_RESPONSES["this week"]
    elif "create" in query or "add" in query or "schedule" in query or "new" in query:
        return CALENDAR_RESPONSES["create"]
    elif "delete" in query or "remove" in query or "cancel" in query:
        return CALENDAR_RESPONSES["delete"]
    elif "update" in query or "change" in query or "edit" in query or "reschedule" in query:
        return CALENDAR_RESPONSES["update"]
    else:
        return CALENDAR_RESPONSES["default"]

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    is_audio: str = Query("false"),
    api_key: Optional[str] = Query(None),
):
    """WebSocket endpoint for Calendar Assistant"""
    # Generate a unique connection ID
    connection_id = f"{session_id}_{uuid.uuid4().hex[:8]}"
    
    # Accept the connection
    await websocket.accept()
    print(f"Client #{connection_id} connected, audio mode: {is_audio}")
    
    # Parse is_audio parameter
    is_audio_mode = is_audio.lower() in ["true", "1", "yes", "y"]
    
    # Send welcome message
    try:
        welcome_message = {
            "mime_type": "text/plain",
            "type": "text/plain",
            "data": "Hello! I'm your scheduling assistant. How can I help you with your calendar today?",
            "content": "Hello! I'm your scheduling assistant. How can I help you with your calendar today?",
            "role": "model"
        }
        print(f"Sending welcome message to client #{connection_id}")
        await websocket.send_text(json.dumps(welcome_message))
        print(f"Sending turn_complete after welcome to client #{connection_id}")
        await websocket.send_text(json.dumps({"turn_complete": True}))
        print(f"Welcome message sequence complete for client #{connection_id}")
    except Exception as e:
        print(f"Error sending welcome message: {e}")
    
    try:
        # Process messages until client disconnects
        while True:
            try:
                # Receive message from client
                message_json = await websocket.receive_text()
                print(f"Message received from {connection_id}: {message_json[:100]}...")
                
                # Parse the message
                message = json.loads(message_json)
                message_type = message.get("type") or message.get("mime_type")
                message_data = message.get("data") or message.get("content") or ""
                
                # Skip ping messages but send acknowledgment
                if message_type == "ping":
                    print(f"Received ping from {connection_id}, acknowledging")
                    try:
                        # Send a ping acknowledgment
                        await websocket.send_text(json.dumps({"type": "pong"}))
                    except Exception as e:
                        print(f"Error sending ping acknowledgment: {e}")
                    continue
                
                # Process audio end marker
                if message_data == "END_OF_AUDIO":
                    print(f"End of audio received from {connection_id}")
                    continue
                    
                print(f"Processing user message: '{message_data}' from {connection_id}")
                
                # Generate a response based on the message
                response_text = get_calendar_response(message_data)
                print(f"Generated response for '{message_data}': '{response_text}'")
                
                # Use a try-except block to handle potential WebSocket disconnects
                try:
                    # First send the text response
                    response = {
                        "mime_type": "text/plain",
                        "type": "text/plain",
                        "data": response_text,
                        "content": response_text,
                        "role": "model"
                    }
                    
                    print(f"Sending response to {connection_id}: {response_text}")
                    await websocket.send_text(json.dumps(response))
                    
                    # Small delay to ensure messages are processed in order
                    await asyncio.sleep(0.2)
                    
                    # Then send turn complete signal
                    print(f"Sending turn_complete to {connection_id}")
                    await websocket.send_text(json.dumps({"turn_complete": True}))
                    
                    print(f"Full response sequence completed for {connection_id}")
                except WebSocketDisconnect:
                    print(f"Client disconnected during response: {connection_id}")
                    raise
                except Exception as e:
                    print(f"Error sending response: {e}")
                    import traceback
                    traceback.print_exc()
                
            except WebSocketDisconnect:
                print(f"Client #{connection_id} disconnected")
                break
            except json.JSONDecodeError as e:
                print(f"Error parsing message: {e}")
                continue
            except Exception as e:
                print(f"Error processing message: {e}")
                break
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        print(f"Connection {connection_id} closed")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8081))
    uvicorn.run("app.standalone_websocket:app", host="0.0.0.0", port=port, reload=True)
