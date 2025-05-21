"""
Focused fix for audio input handling in ADK Voice Agent
"""

import asyncio
import base64
import json
import os
import time
import uuid
from pathlib import Path
from typing import AsyncIterable, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from starlette.status import HTTP_401_UNAUTHORIZED

# Set the path to credentials.json for Google Calendar API
credentials_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'credentials.json')
if os.path.exists(credentials_path):
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
    print(f"Set GOOGLE_APPLICATION_CREDENTIALS to: {credentials_path}")
else:
    print(f"Warning: credentials.json not found at {credentials_path}")

from google.adk.agents import LiveRequestQueue
from google.adk.agents.run_config import RunConfig
from google.adk.events.event import Event
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types
from starlette.status import HTTP_401_UNAUTHORIZED

from app.jarvis.agent import root_agent

# Load environment variables
load_dotenv()

APP_NAME = "ADK Voice Agent"
session_service = InMemorySessionService()

# Configuration
API_KEY = os.getenv("API_KEY", "development-key")  # Set a secure API key in production
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

# Session store to track active sessions
active_sessions: Dict[str, Dict] = {}


async def get_agent_session(session_id: str, connection_id: str, is_audio: bool = False):
    """Gets or creates an agent session with a fresh event stream for each connection"""
    # Check if we already have a session for this user
    if session_id not in active_sessions:
        # First time user - create a completely new session
        print(f"Creating brand new session for {session_id}")
        
        # Create a Session with InMemorySessionService
        adk_session = session_service.create_session(
            app_name=APP_NAME,
            user_id=session_id,
            session_id=session_id,
        )
        
        # Create a Runner with the session service
        runner = Runner(
            app_name=APP_NAME,
            agent=root_agent,
            session_service=session_service,
        )
        
        # Create speech config
        speech_config = types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck")
            )
        )
        
        # Create the base session object to track data
        active_sessions[session_id] = {
            "adk_session": adk_session,
            "runner": runner,
            "speech_config": speech_config,
            "is_audio": is_audio,
            "created_at": time.time(),
            "connections": {},
            "request_queues": {},
        }
    
    # We now have a base session - create a new request queue for this connection
    print(f"Creating fresh request queue for connection {connection_id}")
    live_request_queue = LiveRequestQueue()
    
    # Store the request queue for this connection
    active_sessions[session_id]["request_queues"][connection_id] = live_request_queue
    
    # Create proper run config with audio settings for this connection
    config = {
        # Set response modalities based on audio mode
        "response_modalities": ["AUDIO"] if is_audio else ["TEXT"],
        "speech_config": active_sessions[session_id]["speech_config"],
    }
    
    # Always enable audio transcription regardless of mode
    config["input_audio_transcription"] = {}
    
    # Only set output audio for audio mode to avoid validation errors
    if is_audio:
        # When in audio mode, enable speech synthesis
        config["output_audio_synthesis"] = {}
        
    print(f"Creating run config for {connection_id} with: {config}")
    run_config = RunConfig(**config)
    
    # Create a fresh event stream for this connection
    # This is the key to fixing the "asynchronous generator is already running" error
    live_events = active_sessions[session_id]["runner"].run_live(
        session=active_sessions[session_id]["adk_session"],
        live_request_queue=live_request_queue,
        run_config=run_config,
    )
    
    # Track this connection
    active_sessions[session_id]["connections"][connection_id] = {
        "last_active": time.time(),
        "is_audio": is_audio,
    }
    
    print(f"Created fresh event stream for {connection_id}")
    return live_events, live_request_queue


def handle_audio_data(data, connection_id, mime_type="audio/pcm"):
    """Process audio data with proper error handling"""
    print(f"[AUDIO INFO]: Processing audio data of length {len(data)} for {connection_id}")
    
    # Check if this is an end marker
    if not data or data == "END_OF_AUDIO" or data == "end":
        print(f"[AUDIO INFO]: Detected end-of-audio marker for {connection_id}")
        return b"", True
    
    # Try base64 decoding
    try:
        decoded_data = base64.b64decode(data)
        print(f"[AUDIO INFO]: Successfully decoded base64 data of size {len(decoded_data)} bytes for {connection_id}")
        return decoded_data, False
    except Exception as e:
        print(f"[AUDIO WARNING]: Base64 decode failed: {e} for {connection_id}")
        
        # If base64 decoding fails, try direct binary handling
        try:
            # Handle string data by encoding to bytes
            if isinstance(data, str):
                binary_data = data.encode('latin1')
            else:
                binary_data = data
                
            print(f"[AUDIO INFO]: Using direct binary data of size {len(binary_data)} bytes for {connection_id}")
            return binary_data, False
        except Exception as e2:
            print(f"[AUDIO ERROR]: Failed to process audio data: {e2} for {connection_id}")
            return b"", True


# Create FastAPI app
app = FastAPI(title="ADK Voice Agent API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Key security
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: str = Depends(api_key_header)):
    """Verify API key"""
    if api_key != API_KEY:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return api_key


@app.get("/api")
async def root():
    """API root endpoint"""
    return {
        "name": APP_NAME,
        "endpoints": {
            "api": "/api",
            "status": "/api/status",
            "websocket": "/ws/{session_id}?is_audio=true&api_key=your-api-key",
        },
    }


@app.get("/status")
async def status_legacy():
    """Legacy status endpoint for backward compatibility"""
    has_gemini_key = bool(os.getenv("GOOGLE_API_KEY"))
    has_calendar_creds = bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
    
    return {
        "status": "online",
        "has_gemini_key": has_gemini_key,
        "has_calendar_credentials": has_calendar_creds,
    }


@app.get("/api/status")
async def status():
    """API status endpoint for Next.js compatibility"""
    has_gemini_key = bool(os.getenv("GOOGLE_API_KEY"))
    has_calendar_creds = bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
    
    return {
        "status": "online",
        "has_gemini_key": has_gemini_key,
        "has_calendar_credentials": has_calendar_creds,
    }


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    is_audio: str = Query("false"),  # Default to false
    api_key: Optional[str] = Query(None),
    x_api_key: Optional[str] = Header(None),
):
    """WebSocket endpoint with improved audio handling"""
    connection_id = f"{session_id}_{is_audio}_{uuid.uuid4().hex[:8]}"
    
    # For development, bypass API key validation
    print(f"API authentication bypassed for development on connection {connection_id}")
    
    await websocket.accept()
    print(f"Client #{connection_id} connected, audio mode: {is_audio}")
    
    # Parse is_audio parameter properly - handle various formats
    is_audio_mode = False
    if is_audio and is_audio.lower() in ["true", "1", "yes", "y"]:
        is_audio_mode = True
    print(f"Setting up session with audio mode: {is_audio_mode}")
    
    # Send welcome message
    welcome_sent = False
    if session_id not in active_sessions:
        welcome_sent = True
        try:
            print(f"Sending welcome message to {connection_id}")
            welcome_message = {
                "mime_type": "text/plain",
                "type": "text/plain",
                "data": "Hello! I'm your scheduling assistant. How can I help you with your calendar today?",
                "content": "Hello! I'm your scheduling assistant. How can I help you with your calendar today?",
                "role": "model"
            }
            await websocket.send_text(json.dumps(welcome_message))
            await websocket.send_text(json.dumps({"turn_complete": True}))
            print(f"Welcome message sent to {connection_id}")
        except Exception as e:
            print(f"Error sending welcome message: {e}")
    
    try:
        # Get or create agent session
        live_events, live_request_queue = await get_agent_session(session_id, connection_id, is_audio_mode)
        
        # Handle client-to-agent communication
        client_to_agent_task = asyncio.create_task(
            handle_client_to_agent(websocket, live_request_queue, connection_id, is_audio_mode)
        )
        
        # Handle agent-to-client communication
        agent_to_client_task = asyncio.create_task(
            handle_agent_to_client(websocket, live_events, connection_id)
        )
        
        # Wait for client_to_agent_task to complete (when client disconnects)
        await client_to_agent_task
        
    except WebSocketDisconnect:
        print(f"Client #{connection_id} disconnected")
    except Exception as e:
        print(f"Error in websocket endpoint: {e}")
    finally:
        # Clean up connection tracking
        if session_id in active_sessions and connection_id in active_sessions[session_id]["connections"]:
            del active_sessions[session_id]["connections"][connection_id]
            print(f"Removed connection tracking for {connection_id}")
        print(f"Client #{connection_id} websocket connection ended")


async def handle_client_to_agent(
    websocket: WebSocket, 
    live_request_queue: LiveRequestQueue, 
    connection_id: str,
    is_audio_mode: bool
):
    """Handle messages from client to agent with improved audio handling"""
    try:
        while True:
            # Receive message from client
            message_json = await websocket.receive_text()
            print(f"[RAW MESSAGE]: {message_json[:200]}... for {connection_id}")
            
            try:
                message = json.loads(message_json)
            except json.JSONDecodeError as je:
                print(f"JSON error: {je} for {connection_id}")
                continue
                
            # Handle authentication message
            if message.get("type") == "auth":
                print(f"[AUTH]: Received auth message for {connection_id}")
                await websocket.send_text(json.dumps({"type": "auth_success"}))
                continue
                
            # Get message type and data
            mime_type = message.get("mime_type") or message.get("type")
            data = message.get("data") or message.get("content")
            
            if not mime_type or data is None:
                print(f"Invalid message format for {connection_id}")
                continue
                
            # Get role (default to user)
            role = message.get("role", "user")
            
            # Handle text message
            if mime_type == "text/plain":
                print(f"[TEXT]: Sending text to agent: {data} for {connection_id}")
                
                try:
                    content = types.Content(
                        role=role, 
                        parts=[types.Part.from_text(text=data)]
                    )
                    live_request_queue.send_content(content=content)
                    print(f"Text sent successfully for {connection_id}")
                except Exception as e:
                    print(f"Error sending text to agent: {e} for {connection_id}")
                    await send_error_response(websocket, f"Error processing text: {e}")
                    
            # Handle audio message
            elif mime_type in ["audio/pcm", "audio/wav", "audio/webm"]:
                # Force is_audio_mode to true when receiving audio data
                if not is_audio_mode:
                    print(f"[AUDIO]: Detected audio input but is_audio_mode was false. Upgrading to audio mode for {connection_id}")
                    is_audio_mode = True
                    
                    # No need to get a fresh connection - we'll handle audio with the current connection
                    # This prevents scope issues with session_id
                print(f"[AUDIO]: Received audio data with mime type: {mime_type} for {connection_id}")
                
                try:
                    # Process the audio data
                    audio_data, is_end_marker = handle_audio_data(data, connection_id, mime_type)
                    
                    if is_end_marker:
                        # Handle end-of-audio marker
                        print(f"[AUDIO]: End of audio detected for {connection_id}")
                        
                        # Send empty audio blob to signal end of stream
                        live_request_queue.send_realtime(types.Blob(data=b"", mime_type="audio/pcm"))
                        
                        # Send a special text message to trigger response generation
                        end_content = types.Content(
                            role="user",
                            parts=[types.Part.from_text(text="_END_OF_AUDIO_PROCESSING_")]
                        )
                        live_request_queue.send_content(content=end_content)
                        
                        print(f"[AUDIO]: End markers sent for {connection_id}")
                    else:
                        # Send normal audio data
                        blob = types.Blob(data=audio_data, mime_type="audio/pcm")
                        live_request_queue.send_realtime(blob)
                        print(f"[AUDIO]: Audio chunk sent ({len(audio_data)} bytes) for {connection_id}")
                        
                except Exception as e:
                    print(f"[AUDIO ERROR]: {e} for {connection_id}")
                    await send_error_response(websocket, f"Error processing audio: {e}")
            else:
                print(f"Unsupported mime type: {mime_type} for {connection_id}")
                await send_error_response(websocket, f"Unsupported format: {mime_type}")
                
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for {connection_id}")
    except Exception as e:
        print(f"Error in client-to-agent messaging: {e} for {connection_id}")


async def handle_agent_to_client(
    websocket: WebSocket, 
    live_events: AsyncIterable[Event | None], 
    connection_id: str
):
    """Handle responses from agent to client with improved audio handling"""
    try:
        print(f"[AGENT]: Starting agent-to-client messaging for {connection_id}")
        event_count = 0
        final_text_message = None
        
        async for event in live_events:
            event_count += 1
            print(f"[AGENT]: Received event #{event_count} for {connection_id}")
            
            if event is None:
                print(f"[AGENT]: Empty event for {connection_id}")
                continue
                
            # Handle turn completion
            if event.turn_complete or event.interrupted:
                if final_text_message:
                    await websocket.send_text(json.dumps(final_text_message))
                    final_text_message = None
                    
                await websocket.send_text(json.dumps({
                    "turn_complete": event.turn_complete,
                    "interrupted": event.interrupted
                }))
                print(f"[AGENT]: Turn complete sent for {connection_id}")
                continue
                
            # Skip events without content or parts
            if not event.content or not event.content.parts:
                continue
                
            part = event.content.parts[0]
            if not part:
                continue
                
            # Handle different types of responses
            try:
                # Handle text response - only send non-partial
                if part.text is not None and not event.partial:
                    print(f"[AGENT]: Text response: {part.text[:50]}... for {connection_id}")
                    final_text_message = {
                        "mime_type": "text/plain",
                        "type": "text/plain",
                        "data": part.text,
                        "content": part.text,
                        "role": "model",
                        "partial": False
                    }
                
                # Handle audio response
                elif hasattr(part, 'audio_blob') and part.audio_blob is not None:
                    print(f"[AGENT]: Audio response: {len(part.audio_blob.data)} bytes for {connection_id}")
                    await websocket.send_text(json.dumps({
                        "mime_type": part.audio_blob.mime_type,
                        "type": part.audio_blob.mime_type,
                        "data": base64.b64encode(part.audio_blob.data).decode("utf-8"),
                        "content": "Audio response",
                        "role": "model",
                        "partial": event.partial
                    }))
            except Exception as part_error:
                print(f"[AGENT]: Error processing part: {part_error} for {connection_id}")
                
    except Exception as e:
        print(f"[AGENT ERROR]: {e} for {connection_id}")
        
        # Try to send error message
        try:
            await send_error_response(websocket, "Error processing your request")
        except:
            pass


async def send_error_response(websocket: WebSocket, message: str):
    """Send an error response to the client"""
    try:
        await websocket.send_text(json.dumps({
            "mime_type": "text/plain",
            "type": "text/plain",
            "data": message,
            "content": message,
            "role": "model"
        }))
        await websocket.send_text(json.dumps({"turn_complete": True}))
    except Exception as e:
        print(f"Error sending error response: {e}")


# Static files
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", response_class=FileResponse)
async def get_index():
    """Serve the static UI"""
    return FileResponse(STATIC_DIR / "index.html")


# For Google Cloud Run
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8081))
    uvicorn.run("app.main_audio_config_fix:app", host="0.0.0.0", port=port, reload=False)
