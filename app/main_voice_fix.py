import asyncio
import base64
import json
import os
import time
from pathlib import Path
from typing import AsyncIterable, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles

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

# Create FastAPI app
app = FastAPI(title="ADK Voice Agent API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # Use the actual allowed origins from env
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session store to track active sessions
active_sessions: Dict[str, Dict] = {}


def start_agent_session(session_id: str, is_audio: bool = False):
    """Starts an agent session"""
    # Create a Session
    session = session_service.create_session(
        app_name=APP_NAME,
        user_id=session_id,
        session_id=session_id,
    )

    # Create a Runner
    runner = Runner(
        app_name=APP_NAME,
        agent=root_agent,
        session_service=session_service,
    )

    # Set response modality
    modality = "AUDIO" if is_audio else "TEXT"

    # Create speech config with voice settings
    speech_config = types.SpeechConfig(
        voice_config=types.VoiceConfig(
            # Available voices: Puck, Charon, Kore, Fenrir, Aoede, Leda, Orus, and Zephyr
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck")
        )
    )

    # Create run config with basic settings
    config = {
        "response_modalities": [modality], 
        "speech_config": speech_config
    }

    # Add input_audio_transcription when audio is enabled
    if is_audio:
        config["input_audio_transcription"] = {}
        config["output_audio_transcription"] = {}

    run_config = RunConfig(**config)

    # Create a LiveRequestQueue for this session
    live_request_queue = LiveRequestQueue()

    # Start agent session
    live_events = runner.run_live(
        session=session,
        live_request_queue=live_request_queue,
        run_config=run_config,
    )
    
    # Store session data
    active_sessions[session_id] = {
        "live_events": live_events,
        "live_request_queue": live_request_queue,
        "is_audio": is_audio,
        "created_at": asyncio.get_event_loop().time(),
    }
    
    return live_events, live_request_queue


async def agent_to_client_messaging(
    websocket: WebSocket, live_events: AsyncIterable[Event | None]
):
    """Agent to client communication"""
    print("[AGENT]: Starting agent-to-client messaging loop...")
    
    # Handle missing credentials by sending a fallback response
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        print("[AGENT WARNING]: Google Application Credentials not found")
        # Send a fallback message if the credentials are missing
        try:
            fallback_message = {
                "mime_type": "text/plain",
                "type": "text/plain",
                "data": "I'm having trouble accessing the calendar service right now. For full calendar functionality, please ensure the GOOGLE_APPLICATION_CREDENTIALS environment variable is set.",
                "content": "I'm having trouble accessing the calendar service right now. For full calendar functionality, please ensure the GOOGLE_APPLICATION_CREDENTIALS environment variable is set.",
                "role": "model"
            }
            await websocket.send_text(json.dumps(fallback_message))
            await websocket.send_text(json.dumps({"turn_complete": True}))
            print("[AGENT]: Sent fallback message due to missing credentials")
        except Exception as e:
            print(f"[AGENT ERROR]: Error sending fallback message: {e}")
    
    try:
        event_count = 0
        print("[AGENT]: Waiting for events from the agent...")
        final_text_message = None
        
        async for event in live_events:
            event_count += 1
            print(f"[AGENT DEBUG]: Received event #{event_count}")
            
            if event is None:
                print("[AGENT DEBUG]: Event is None, skipping")
                continue

            # Log the event type for debugging
            print(f"[AGENT DEBUG]: Event type: {type(event).__name__}, partial: {event.partial}")

            # If the turn complete or interrupted, send it
            if event.turn_complete or event.interrupted:
                # If we have accumulated a final text message, send it now
                if final_text_message:
                    await websocket.send_text(json.dumps(final_text_message))
                    final_text_message = None
                
                message = {
                    "turn_complete": event.turn_complete,
                    "interrupted": event.interrupted,
                }
                await websocket.send_text(json.dumps(message))
                print(f"[AGENT TO CLIENT]: Turn complete: {message}")
                continue

            # Debug print the full event when available
            try:
                print(f"[AGENT DEBUG]: Event content: {event.content}")
            except Exception as e:
                print(f"[AGENT DEBUG]: Could not print event content: {e}")
                
            # Read the Content and its first Part
            if not event.content:
                print("[AGENT DEBUG]: No content in event")
                continue
                
            if not event.content.parts:
                print("[AGENT DEBUG]: No parts in event content")
                continue
                
            part = event.content.parts[0]
            if not part:
                print("[AGENT DEBUG]: First part is empty")
                continue

            # Make sure we have a valid Part
            try:
                # We only want to send user-visible final text content to the client
                # This prevents internal processing details from showing up in the UI
                if part.text is not None and not event.partial:
                    # Only send non-partial (final) text responses
                    # This accumulates the final message and only sends at the end
                    # or when a new one arrives
                    final_text_message = {
                        "mime_type": "text/plain",
                        "type": "text/plain",
                        "data": part.text,
                        "content": part.text,
                        "role": "model",
                        "partial": False,
                    }
                    print(f"[AGENT DEBUG]: Accumulated final text: {part.text[:50]}...")
                    
                elif hasattr(part, 'audio_blob') and part.audio_blob is not None:
                    # Audio response - send immediately
                    print(f"[AGENT TO CLIENT]: Sending audio of size: {len(part.audio_blob.data)} bytes")
                    message = {
                        "mime_type": part.audio_blob.mime_type,
                        "type": part.audio_blob.mime_type,
                        "data": base64.b64encode(part.audio_blob.data).decode("utf-8"),
                        "content": "Audio response",
                        "role": "model",
                        "partial": event.partial,
                    }
                    await websocket.send_text(json.dumps(message))
                elif hasattr(part, 'func_call') and part.func_call is not None:
                    # Function call - don't send to client UI
                    print(f"[AGENT DEBUG]: Function call: {part.func_call}")
                elif hasattr(part, 'executable_code') and part.executable_code is not None:
                    # Handle executable code - don't send to client UI
                    print(f"[AGENT DEBUG]: Executable code: {part.executable_code}")
                elif hasattr(part, 'function_response') and part.function_response is not None:
                    # Handle function response - don't send to client UI
                    print(f"[AGENT DEBUG]: Function response: {part.function_response}")
                elif hasattr(part, 'code_execution_result') and part.code_execution_result is not None:
                    # Handle code execution result - don't send to client UI
                    print(f"[AGENT DEBUG]: Code execution result: {part.code_execution_result}")
                else:
                    # Other part types - log only, don't send to client
                    print(f"[AGENT DEBUG]: Other part type: {type(part).__name__}")
            except Exception as part_error:
                print(f"[AGENT DEBUG]: Error processing part: {part_error}")
                # Continue without failing the entire loop
                
    except Exception as e:
        print(f"[AGENT TO CLIENT ERROR]: Error in agent-to-client messaging: {e}")
        # Try to send an error message to the client
        try:
            error_message = {
                "mime_type": "text/plain",
                "type": "text/plain",
                "data": "I'm having trouble processing your request right now. Please try again.",
                "content": "I'm having trouble processing your request right now. Please try again.",
                "role": "model"
            }
            await websocket.send_text(json.dumps(error_message))
            await websocket.send_text(json.dumps({"turn_complete": True}))
        except:
            # If even sending the error message fails, we've lost the connection
            pass


async def client_to_agent_messaging(
    websocket: WebSocket, live_request_queue: LiveRequestQueue
):
    """Client to agent communication"""
    try:
        while True:
            # Decode JSON message
            try:
                message_json = await websocket.receive_text()
                print(f"[RAW MESSAGE]: {message_json}")
                message = json.loads(message_json)
                print(f"[RECEIVED MESSAGE]: {message}")
            except json.JSONDecodeError as je:
                print(f"[JSON ERROR]: Could not parse message: {je}")
                print(f"[JSON ERROR]: Raw content: {message_json}")
                continue
                
            # Handle authentication message
            if message.get("type") == "auth":
                print(f"[CLIENT AUTH]: Received authentication message")
                await websocket.send_text(json.dumps({"type": "auth_success"}))
                continue
                
            # Get message type - support both mime_type and type fields
            mime_type = message.get("mime_type") or message.get("type")
            if not mime_type:
                print(f"[CLIENT ERROR]: No mime_type or type in message: {message}")
                continue
                
            # Get message data - support both data and content fields
            data = message.get("data") or message.get("content")
            if data is None:
                print(f"[CLIENT ERROR]: No data or content in message: {message}")
                continue
                
            # Get role with default
            role = message.get("role", "user")  # Default to 'user' if role is not provided

            # Send the message to the agent
            if mime_type == "text/plain":
                # Send a text message to the agent
                print(f"[CLIENT TO AGENT]: Sending text to agent: {data}")
                
                # Try to send the message to the agent
                try:
                    content = types.Content(role=role, parts=[types.Part.from_text(text=data)])
                    live_request_queue.send_content(content=content)
                    print(f"[CLIENT TO AGENT]: Text sent successfully to agent: {data}")
                except Exception as e:
                    print(f"[CLIENT TO AGENT ERROR]: Failed to send to agent: {e}")
                    
                    # Send a fallback response if the agent fails
                    await websocket.send_text(json.dumps({
                        "mime_type": "text/plain",
                        "type": "text/plain",
                        "data": "I'm sorry, I'm having trouble processing your request right now.",
                        "content": "I'm sorry, I'm having trouble processing your request right now.",
                        "role": "model"
                    }))
                    await websocket.send_text(json.dumps({"turn_complete": True}))
                
            elif mime_type == "audio/pcm" or mime_type == "audio/wav" or mime_type == "audio/webm":
                # Send audio data
                try:
                    print(f"[CLIENT TO AGENT]: Received audio data with mime type: {mime_type}")
                    print(f"[CLIENT TO AGENT]: Decoding audio data of length: {len(data)}")
                    
                    # For WebM, we need to ensure the data is handled as base64
                    try:
                        decoded_data = base64.b64decode(data)
                        print(f"[CLIENT TO AGENT]: Decoded audio data of size: {len(decoded_data)} bytes")
                    except Exception as decode_error:
                        print(f"[AUDIO ERROR]: Failed to decode base64: {decode_error}")
                        print("[AUDIO INFO]: Trying direct binary handling...")
                        # If it's not base64 encoded, use it directly
                        decoded_data = data.encode('latin1') if isinstance(data, str) else data
                        print(f"[CLIENT TO AGENT]: Using direct data of size: {len(decoded_data)} bytes")

                    # Send the audio data to the agent
                    blob = types.Blob(data=decoded_data, mime_type="audio/pcm")
                    print(f"[CLIENT TO AGENT]: Created blob with mime_type: {blob.mime_type}")
                    
                    # Send audio as realtime data
                    live_request_queue.send_realtime(blob)
                    print(f"[CLIENT TO AGENT]: Audio sent successfully: {len(decoded_data)} bytes")
                    
                except Exception as audio_error:
                    print(f"[AUDIO ERROR]: Failed to process audio: {audio_error}")
                    
                    # Send a fallback response if audio processing fails
                    await websocket.send_text(json.dumps({
                        "mime_type": "text/plain",
                        "type": "text/plain",
                        "data": f"I'm sorry, I couldn't process your audio message. Error: {str(audio_error)}",
                        "content": f"I'm sorry, I couldn't process your audio message. Error: {str(audio_error)}",
                        "role": "model"
                    }))
                    await websocket.send_text(json.dumps({"turn_complete": True}))
            else:
                print(f"[CLIENT WARNING]: Unsupported mime type: {mime_type}")
                
                # Send an unsupported format message
                await websocket.send_text(json.dumps({
                    "mime_type": "text/plain",
                    "type": "text/plain",
                    "data": f"I don't support messages with type '{mime_type}'. Please send text or audio.",
                    "content": f"I don't support messages with type '{mime_type}'. Please send text or audio.",
                    "role": "model"
                }))
                await websocket.send_text(json.dumps({"turn_complete": True}))
    except WebSocketDisconnect:
        print("WebSocket disconnected during client-to-agent messaging")
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON message: {e}")
    except Exception as e:
        print(f"Error in client-to-agent messaging: {e}")


# API Endpoints
@app.get("/api")
async def root():
    """API root endpoint"""
    return {
        "name": APP_NAME,
        "endpoints": {
            "api": "/api",
            "status": "/api/status",
            "websocket": "/ws/{session_id}?is_audio=false&api_key=your-api-key",
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
    """API status endpoint - accessible without authentication for development"""
    has_gemini_key = bool(os.getenv("GOOGLE_API_KEY"))
    has_calendar_creds = bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
    
    return {
        "status": "online",
        "has_gemini_key": has_gemini_key,
        "has_calendar_credentials": has_calendar_creds,
    }


# Static files
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", response_class=FileResponse)
async def get_index():
    # Serve the UI from static/index.html
    return FileResponse(STATIC_DIR / "index.html")


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    is_audio: str = Query(...),
    api_key: Optional[str] = Query(None),
    x_api_key: Optional[str] = Header(None),
):
    """Client websocket endpoint with API key validation"""
    # Create a unique connection ID for this specific websocket connection
    connection_id = f"{session_id}_{is_audio}_{id(websocket)}"
    
    # Note: In development, we're bypassing API key validation for easier testing
    # Uncomment for production
    """
    # Validate API key from header OR query parameter
    provided_api_key = x_api_key or api_key
    
    if provided_api_key != API_KEY:
        print(f"Invalid API key provided: {provided_api_key}")
        await websocket.close(code=1008)  # Policy violation
        return
    """
    print(f"API authentication bypassed for development on connection {connection_id}")
        
    # Wait for client connection
    await websocket.accept()
    print(f"Client #{connection_id} connected, audio mode: {is_audio}")
    
    # Send an immediate welcome message to test message flow
    try:
        print(f"DEBUG: Preparing to send welcome message to {connection_id}")
        welcome_message = {
            "mime_type": "text/plain",
            "type": "text/plain",
            "data": "Hello! I'm your scheduling assistant. How can I help you with your calendar today?",
            "content": "Hello! I'm your scheduling assistant. How can I help you with your calendar today?",
            "role": "model"
        }
        print(f"DEBUG: Welcome message prepared: {json.dumps(welcome_message)[:100]}...")
        await websocket.send_text(json.dumps(welcome_message))
        await websocket.send_text(json.dumps({"turn_complete": True}))
        print(f"DEBUG: Welcome message sent successfully to client #{connection_id}")
    except Exception as e:
        print(f"Error sending welcome message: {e}")
    
    is_audio_mode = (is_audio.lower() == "true")
    print(f"Setting up session with audio mode: {is_audio_mode}")
    
    try:
        # Start agent session or get existing one
        if session_id not in active_sessions:
            # First connection for this session - create a new session
            print(f"Creating new agent session for {session_id}")
            live_events, live_request_queue = start_agent_session(
                session_id, is_audio_mode
            )
        else:
            # Get existing session data
            print(f"Reusing existing agent session for {session_id}")
            session_data = active_sessions[session_id]
            live_events = session_data["live_events"]
            live_request_queue = session_data["live_request_queue"]
        
        # For both text and audio connections, use bi-directional messaging
        print(f"Starting tasks for {connection_id}")
        agent_to_client_task = asyncio.create_task(
            agent_to_client_messaging(websocket, live_events)
        )
        client_to_agent_task = asyncio.create_task(
            client_to_agent_messaging(websocket, live_request_queue)
        )
        
        # Wait for client_to_agent_task to complete (when client disconnects)
        await client_to_agent_task
            
    except WebSocketDisconnect:
        print(f"Client #{connection_id} disconnected")
    except Exception as e:
        print(f"Error in websocket endpoint: {e}")
    finally:
        # Don't remove session immediately to allow reconnections
        # In a production app, you might want to add a cleanup job
        # that removes stale sessions after a timeout period
        print(f"Client #{connection_id} websocket connection ended")


# For Google Cloud Run
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8081))
    uvicorn.run("app.main_voice_fix:app", host="0.0.0.0", port=port, reload=False)
