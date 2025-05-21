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
from starlette.websockets import WebSocketState

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

from app.jarvis.agent import root_agent

# Load environment variables
load_dotenv()

APP_NAME = "ADK Voice Agent"
session_service = InMemorySessionService()

# Configuration
API_KEY = os.getenv("API_KEY", "development-key")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

# Session storage
active_sessions = {}

class SessionManager:
    def __init__(self):
        self.sessions = {}
        self.welcomed_sessions = set()
        self.lock = asyncio.Lock()
        
    async def get_or_create_session(self, session_id, connection_id, force_audio_mode=False):
        """Get or create a session with proper audio configuration"""
        async with self.lock:
            # Determine if we need to create a new base session
            if session_id not in self.sessions:
                print(f"Creating new base session for {session_id}")
                
                # Create ADK Session
                adk_session = session_service.create_session(
                    app_name=APP_NAME,
                    user_id=session_id,
                    session_id=session_id,
                )
                
                # Create Runner
                runner = Runner(
                    app_name=APP_NAME,
                    agent=root_agent,
                    session_service=session_service,
                )
                
                # Create Speech Config
                speech_config = types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck")
                    )
                )
                
                # Store session data
                self.sessions[session_id] = {
                    "adk_session": adk_session,
                    "runner": runner,
                    "speech_config": speech_config,
                    "created_at": time.time(),
                    "connections": {},
                    "request_queues": {},
                }
            
            # Create a new request queue for this connection
            live_request_queue = LiveRequestQueue()
            self.sessions[session_id]["request_queues"][connection_id] = live_request_queue
            
            # Track if this is an audio connection
            is_audio = force_audio_mode
            if connection_id in self.sessions[session_id]["connections"]:
                is_audio = self.sessions[session_id]["connections"][connection_id].get("is_audio", force_audio_mode)
            
            # Create run config - ALWAYS enable audio transcription
            # Use string values for response_modalities based on previous working versions
            config = {
                "response_modalities": ["AUDIO"] if is_audio else ["TEXT"],
                "speech_config": self.sessions[session_id]["speech_config"],
                "input_audio_transcription": {},
            }
            
            # Based on Gemini API docs, do not include output_audio_synthesis
            # It appears it's not a valid parameter for RunConfig
                
            print(f"Creating run config for {connection_id}: {config}")
            run_config = RunConfig(**config)
            
            # Create a fresh event stream
            live_events = self.sessions[session_id]["runner"].run_live(
                session=self.sessions[session_id]["adk_session"],
                live_request_queue=live_request_queue,
                run_config=run_config,
            )
            
            # Track connection
            self.sessions[session_id]["connections"][connection_id] = {
                "is_audio": is_audio,
                "last_active": time.time(),
            }
            
            # Determine if welcome message should be sent
            should_send_welcome = False
            if session_id not in self.welcomed_sessions:
                self.welcomed_sessions.add(session_id)
                should_send_welcome = True
                
            return live_events, live_request_queue, should_send_welcome, is_audio
            
    async def update_audio_mode(self, session_id, connection_id, is_audio):
        """Update a connection's audio mode"""
        async with self.lock:
            if session_id in self.sessions and connection_id in self.sessions[session_id]["connections"]:
                self.sessions[session_id]["connections"][connection_id]["is_audio"] = is_audio
                return True
            return False
            
    async def remove_connection(self, session_id, connection_id):
        """Remove a connection"""
        async with self.lock:
            if session_id in self.sessions and connection_id in self.sessions[session_id]["connections"]:
                del self.sessions[session_id]["connections"][connection_id]
                if connection_id in self.sessions[session_id]["request_queues"]:
                    del self.sessions[session_id]["request_queues"][connection_id]
                return True
            return False


# Create session manager
session_manager = SessionManager()

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
    is_audio: str = Query(None),
    api_key: Optional[str] = Query(None),
):
    """WebSocket endpoint with improved audio handling"""
    # Create a unique connection ID
    connection_id = f"{session_id}_{uuid.uuid4().hex[:8]}"
    
    # For development, bypass API key validation
    print(f"API authentication bypassed for development")
    
    # Accept WebSocket connection
    await websocket.accept()
    print(f"Client #{connection_id} connected")
    
    # Parse is_audio parameter, defaulting to false
    is_audio_mode = False
    if is_audio and is_audio.lower() in ["true", "1", "yes", "y"]:
        is_audio_mode = True
    print(f"Initial audio mode: {is_audio_mode}")
    
    try:
        # Initialize session with proper audio configuration
        live_events, live_request_queue, should_send_welcome, is_audio_mode = await session_manager.get_or_create_session(
            session_id, 
            connection_id,
            force_audio_mode=is_audio_mode
        )
        
        # Send welcome message if this is the first connection for the session
        if should_send_welcome:
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
                print(f"Welcome message sent")
            except Exception as e:
                print(f"Error sending welcome message: {e}")
        
        # Create tasks for bidirectional communication
        agent_to_client_task = asyncio.create_task(
            handle_agent_to_client(websocket, live_events, connection_id)
        )
        
        client_to_agent_task = asyncio.create_task(
            handle_client_to_agent(
                websocket, 
                live_request_queue, 
                connection_id, 
                session_id,
                is_audio_mode
            )
        )
        
        # Wait for either task to complete
        done, pending = await asyncio.wait(
            [agent_to_client_task, client_to_agent_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Cancel pending tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
                
    except WebSocketDisconnect:
        print(f"Client #{connection_id} disconnected")
    except Exception as e:
        print(f"Error in websocket endpoint: {e}")
    finally:
        # Clean up
        await session_manager.remove_connection(session_id, connection_id)
        print(f"Connection {connection_id} ended")


async def handle_agent_to_client(websocket, live_events, connection_id):
    """Handle messages from agent to client"""
    try:
        print(f"[AGENT]: Starting agent-to-client messaging for {connection_id}")
        event_count = 0
        final_text_message = None
        
        async for event in live_events:
            # Check if websocket is still connected
            if websocket.client_state != WebSocketState.CONNECTED:
                break
                
            event_count += 1
            print(f"[AGENT]: Received event #{event_count} for {connection_id}")
            
            if event is None:
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
                continue
                
            # Skip events without content
            if not event.content or not event.content.parts:
                continue
                
            part = event.content.parts[0]
            if not part:
                continue
                
            # Handle different response types
            try:
                # Text response - accumulate and send final
                if part.text is not None:
                    # For final text (non-partial), accumulate
                    if not event.partial:
                        final_text_message = {
                            "mime_type": "text/plain",
                            "type": "text/plain",
                            "data": part.text,
                            "content": part.text,
                            "role": "model",
                            "partial": False
                        }
                        print(f"[AGENT]: Text response: {part.text[:50]}... for {connection_id}")
                    
                # Audio response - send immediately
                elif hasattr(part, 'audio_blob') and part.audio_blob is not None:
                    await websocket.send_text(json.dumps({
                        "mime_type": part.audio_blob.mime_type,
                        "type": part.audio_blob.mime_type,
                        "data": base64.b64encode(part.audio_blob.data).decode("utf-8"),
                        "content": "Audio response",
                        "role": "model",
                        "partial": event.partial
                    }))
                    print(f"[AGENT]: Audio response: {len(part.audio_blob.data)} bytes sent")
            except Exception as e:
                print(f"[AGENT]: Error processing response part: {e}")
                
    except asyncio.CancelledError:
        print(f"[AGENT]: Task cancelled for {connection_id}")
    except Exception as e:
        print(f"[AGENT]: Error in agent-to-client messaging: {e}")
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_text(json.dumps({
                    "mime_type": "text/plain",
                    "type": "text/plain",
                    "data": "I'm having trouble processing your request. Please try again.",
                    "content": "I'm having trouble processing your request. Please try again.",
                    "role": "model"
                }))
                await websocket.send_text(json.dumps({"turn_complete": True}))
        except:
            pass


async def handle_client_to_agent(websocket, live_request_queue, connection_id, session_id, is_audio_mode):
    """Handle messages from client to agent"""
    try:
        while True:
            # Check if websocket is still connected
            if websocket.client_state != WebSocketState.CONNECTED:
                break
                
            # Receive message
            try:
                message_json = await websocket.receive_text()
                print(f"[CLIENT]: Received message: {message_json[:100]}... for {connection_id}")
                message = json.loads(message_json)
            except json.JSONDecodeError as e:
                print(f"[CLIENT]: JSON decode error: {e} for {connection_id}")
                continue
                
            # Handle authentication message
            if message.get("type") == "auth":
                print(f"[CLIENT]: Auth message received for {connection_id}")
                await websocket.send_text(json.dumps({"type": "auth_success"}))
                continue
                
            # Get message type
            mime_type = message.get("mime_type") or message.get("type")
            if not mime_type:
                print(f"[CLIENT]: No mime_type in message for {connection_id}")
                continue
                
            # Get message data
            data = message.get("data") or message.get("content")
            if data is None:
                print(f"[CLIENT]: No data in message for {connection_id}")
                continue
                
            # Handle text message
            if mime_type == "text/plain":
                print(f"[CLIENT]: Text message: {data} for {connection_id}")
                
                try:
                    content = types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=data)]
                    )
                    live_request_queue.send_content(content=content)
                    print(f"[CLIENT]: Text sent to agent for {connection_id}")
                except Exception as e:
                    print(f"[CLIENT]: Error sending text: {e} for {connection_id}")
                    
            # Handle audio message
            elif mime_type in ["audio/pcm", "audio/wav", "audio/webm"]:
                print(f"[CLIENT]: Audio message with type {mime_type} for {connection_id}")
                
                # Update audio mode if needed
                if not is_audio_mode:
                    print(f"[CLIENT]: Upgrading to audio mode for {connection_id}")
                    is_audio_mode = True
                    await session_manager.update_audio_mode(session_id, connection_id, True)
                
                try:
                    # Check for end-of-audio marker
                    is_end_marker = False
                    if data == "" or data == "END_OF_AUDIO" or message.get("end_of_audio") == True or len(data) < 10:
                        print(f"[CLIENT]: End of audio detected for {connection_id}")
                        is_end_marker = True
                        
                        # Send end-of-audio markers - only send the empty blob
                        # This signals the end of audio without triggering implicit follow-up queries
                        live_request_queue.send_realtime(types.Blob(data=b"", mime_type="audio/pcm"))
                    else:
                        # Process audio data
                        try:
                            audio_data = base64.b64decode(data)
                            print(f"[CLIENT]: Decoded audio: {len(audio_data)} bytes for {connection_id}")
                        except Exception as e:
                            print(f"[CLIENT]: Base64 decode error: {e} for {connection_id}")
                            if isinstance(data, str):
                                audio_data = data.encode('latin1')
                            else:
                                audio_data = data
                                
                        # Send audio data to agent
                        blob = types.Blob(data=audio_data, mime_type="audio/pcm")
                        live_request_queue.send_realtime(blob)
                        print(f"[CLIENT]: Audio chunk sent: {len(audio_data)} bytes for {connection_id}")
                except Exception as e:
                    print(f"[CLIENT]: Error processing audio: {e} for {connection_id}")
            else:
                print(f"[CLIENT]: Unsupported mime type: {mime_type} for {connection_id}")
                
    except WebSocketDisconnect:
        print(f"[CLIENT]: WebSocket disconnected for {connection_id}")
    except Exception as e:
        print(f"[CLIENT]: Error in client-to-agent messaging: {e} for {connection_id}")


# Static files
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", response_class=FileResponse)
async def get_index():
    """Serve the UI from static/index.html"""
    return FileResponse(STATIC_DIR / "index.html")


# For Google Cloud Run
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8081))
    uvicorn.run("app.main_final_version:app", host="0.0.0.0", port=port, reload=False)
