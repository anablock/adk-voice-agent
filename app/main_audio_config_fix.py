"""
Focused fix for audio input handling in ADK Voice Agent
"""

import os
import time
import json
import uuid
import base64
import asyncio
from io import BytesIO
from typing import Dict, List, Optional, AsyncIterable, Any
from pathlib import Path

# FastAPI imports
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Query, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from starlette.status import HTTP_401_UNAUTHORIZED

# Google ADK imports - handle version differences
try:
    # For newer ADK versions
    from google.adk import AsyncRunner
except ImportError:
    try:
        # For older ADK versions
        from google.adk.runners import AsyncRunner
    except ImportError:
        print("ERROR: Could not import AsyncRunner from google.adk or google.adk.runners")
        raise

# Import other ADK modules with error handling
try:
    from google.adk.agents.run_config import RunConfig
    from google.adk.type_alias import Event, LiveRequestQueue
    import google.adk.types as types
    from google.adk.tools.tool_registry import ToolRegistry
    from google.adk.sessions.session_service import SessionService
    from google.adk.sessions.memory_session_service import MemorySessionService
    from google.adk.sessions.in_memory_session_service import InMemorySessionService
    from google.adk.runners import Runner
except ImportError as e:
    print(f"ERROR: Failed to import ADK modules: {e}")
    raise

# Import Agent
try:
    from app.jarvis.agent import root_agent
except ImportError:
    print("Error importing root_agent. Check that the jarvis module is set up correctly.")
    raise

# Import conversation memory manager
try:
    from app.memory_init import MEMORY, add_system_message, get_session_summary
    print("Conversation memory module loaded successfully")
    HAS_MEMORY = True
except ImportError:
    print("WARNING: Conversation memory module could not be loaded")
    HAS_MEMORY = False

# Set environment variables
credentials_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'credentials.json')
if os.path.exists(credentials_path):
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
    print(f"Set GOOGLE_APPLICATION_CREDENTIALS to: {credentials_path}")
else:
    print(f"Warning: credentials.json not found at {credentials_path}")

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

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
    # Debugging
    print(f"DEBUG: Getting agent session for {session_id} with connection {connection_id}")
    
    try:
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
            print(f"DEBUG: Successfully created new session for {session_id}")
    except Exception as e:
        print(f"ERROR: Failed to create session: {e}")
        import traceback
        traceback.print_exc()
    
    # We now have a base session - create a new request queue for this connection
    print(f"Creating fresh request queue for connection {connection_id}")
    live_request_queue = LiveRequestQueue()
    
    # Store the request queue for this connection
    active_sessions[session_id]["request_queues"][connection_id] = live_request_queue
    
    # Create proper run config with audio settings for this connection
    # Different ADK versions may require slightly different config formats
    try:
        if is_audio:
            # For audio mode, use the full configuration
            config = {
                "response_modalities": ["AUDIO"],
                "speech_config": active_sessions[session_id]["speech_config"],
                # Some ADK versions expect this structure:
                "input_audio_transcription": None,  # Use None instead of empty dict
            }
            print(f"Creating audio run config for {connection_id}")
        else:
            # For text-only mode, use minimal configuration
            config = {
                "response_modalities": ["TEXT"],
            }
            print(f"Creating text-only run config for {connection_id}")
            
        print(f"Config details: {config}")
        run_config = RunConfig(**config)
    except Exception as config_error:
        print(f"Error creating RunConfig: {config_error}")
        # Fallback to simplest possible config
        run_config = RunConfig()
    
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
    
    # Send an immediate welcome message to test message flow
    try:
        print(f"DEBUG: Preparing to send welcome message to {connection_id}")
        welcome_text = "Hello! I'm your scheduling assistant. How can I help you with your calendar today?"
        
        # Store welcome message in conversation memory
        if HAS_MEMORY:
            try:
                # Initialize the session with a welcome message
                add_system_message(session_id, "Session started")
                add_system_message(session_id, f"Connection {connection_id} established with audio mode: {is_audio_mode}")
                # Store the welcome message
                MEMORY.add_message(session_id, "model", welcome_text)
                print(f"[MEMORY]: Initialized session {session_id} with welcome message")
            except Exception as mem_err:
                print(f"[ERROR] Failed to store welcome message in memory: {mem_err}")
        
        welcome_message = {
            "mime_type": "text/plain",
            "type": "text/plain",
            "data": welcome_text,
            "content": welcome_text,
            "role": "model"
        }
        await websocket.send_text(json.dumps(welcome_message))
        await websocket.send_text(json.dumps({"turn_complete": True}))
        print(f"DEBUG: Welcome message sent successfully to client #{connection_id}")
    except Exception as e:
        print(f"Error sending welcome message: {e}")
    
    try:
        # Get or create agent session
        live_events, live_request_queue = await get_agent_session(session_id, connection_id, is_audio_mode)
        
        # Handle client-to-agent communication with session_id for conversation memory
        client_to_agent_task = asyncio.create_task(
            handle_client_to_agent(websocket, live_request_queue, connection_id, is_audio_mode, session_id)
        )
        
        # Handle agent-to-client communication with session_id for conversation memory
        agent_to_client_task = asyncio.create_task(
            handle_agent_to_client(websocket, live_events, connection_id, session_id)
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
    is_audio_mode: bool,
    session_id: str = None
):
    """Handle messages from client to agent with improved error handling and conversation memory"""
    
    # Set up retry counters and backoff timing
    max_retries = 3
    retry_delay_base = 1.0  # seconds
    
    # Import conversation memory module
    try:
        from app.conversation_memory import conversation_memory
        has_memory = True
    except ImportError:
        print(f"[WARNING] Conversation memory module not available for {connection_id}")
        has_memory = False
    
    try:
        print(f"[CLIENT]: Starting client-to-agent messaging for {connection_id}, audio mode: {is_audio_mode}")
        
        # Process messages until client disconnects
        while True:
            retry_count = 0
            message = None
            
            # Receive message with retry logic
            while retry_count <= max_retries:
                try:
                    # Receive message from client
                    message_json = await websocket.receive_text()
                    print(f"[RAW MESSAGE]: {message_json[:200]}... for {connection_id}")
                    
                    try:
                        message = json.loads(message_json)
                    except json.JSONDecodeError as je:
                        print(f"[ERROR] JSON parsing error for {connection_id}: {je}")
                        await send_error_message(websocket, "Could not understand the message format. Please try again.")
                        continue
                    
                    # Debug message contents
                    print(f"[DEBUG] Message type: {message.get('type') or message.get('mime_type')}")
                    print(f"[DEBUG] Message role: {message.get('role')}")
                    
                    # Successfully received message, break retry loop
                    break
                    
                except WebSocketDisconnect:
                    print(f"[INFO] Client disconnected: {connection_id}")
                    # Don't retry on intentional disconnect
                    return
                    
                except Exception as e:
                    retry_count += 1
                    if retry_count > max_retries:
                        print(f"[ERROR] Failed to receive message after {max_retries} retries: {e}")
                        await send_error_message(websocket, "Connection issues detected. Please check your network.")
                        break
                    else:
                        retry_delay = retry_delay_base * (2 ** (retry_count - 1))  # Exponential backoff
                        print(f"[WARN] Error receiving message (attempt {retry_count}/{max_retries}): {e}. Retrying in {retry_delay:.1f}s")
                        await asyncio.sleep(retry_delay)
            
            # If we exhausted all retries or no message received, break the main loop
            if retry_count > max_retries or not message:
                break
                
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
                
                # Store message in conversation memory using the global memory system
                if HAS_MEMORY and session_id:
                    try:
                        # Use the global MEMORY instance
                        MEMORY.add_message(session_id, role, data)
                        print(f"[MEMORY]: Stored user message for session {session_id}")
                        
                        # Also try to extract entities from user messages
                        if "tomorrow" in data.lower():
                            MEMORY.add_entity(session_id, "date", "tomorrow")
                        elif "next week" in data.lower():
                            MEMORY.add_entity(session_id, "date", "next week")
                        
                        # Log memory state
                        session_summary = get_session_summary(session_id)
                        print(f"[MEMORY]: Session state after user message: {session_summary}")
                    except Exception as mem_err:
                        print(f"[ERROR] Failed to store message in memory: {mem_err}")
                
                try:
                    content = types.Content(
                        role=role, 
                        parts=[types.Part.from_text(text=data)]
                    )
                    live_request_queue.send_content(content=content)
                    print(f"Text sent successfully for {connection_id}")
                except Exception as e:
                    print(f"[ERROR] Error sending text to agent: {e} for {connection_id}")
                    await send_error_message(websocket, "There was a problem processing your message. Please try again.")
                    continue
                    
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
    connection_id: str,
    session_id: str = None
):
    """Handle responses from agent to client with improved error handling and conversation memory"""
    watchdog_task = None
    
    # Import conversation memory module
    try:
        from app.conversation_memory import conversation_memory
        has_memory = True
    except ImportError:
        print(f"[WARNING] Conversation memory module not available for {connection_id}")
        has_memory = False
    try:
        print(f"[AGENT]: Starting agent-to-client messaging for {connection_id}")
        event_count = 0
        final_text_message = None
        has_sent_content = False
        response_timeout = False
        last_event_time = time.time()
        timeout_threshold = 20.0  # seconds
        
        # Set up a watchdog task to monitor response timeouts
        async def response_watchdog():
            nonlocal response_timeout
            while not response_timeout and not has_sent_content:
                await asyncio.sleep(1.0)
                current_time = time.time()
                elapsed = current_time - last_event_time
                if elapsed > timeout_threshold:
                    print(f"[WARN] Response timeout detected for {connection_id} after {elapsed:.1f}s")
                    response_timeout = True
                    try:
                        await send_error_message(websocket, "The response is taking longer than expected. Please try a simpler query.")
                    except Exception as e:
                        print(f"[ERROR] Failed to send timeout message: {e}")
                    return
        
        # Start watchdog in background
        watchdog_task = asyncio.create_task(response_watchdog())
        
        # Debug logging
        print(f"[DEBUG] Starting to process agent responses for {connection_id}")
        
        # Process events from the agent
        async for event in live_events:
            # Update watchdog timer
            last_event_time = time.time()
            
            # Process event
            event_count += 1
            print(f"[AGENT]: Received event #{event_count} for {connection_id}")
            
            if event is None:
                print(f"[AGENT]: Empty event for {connection_id}")
                continue
                
            # Check for error event
            if hasattr(event, 'error') and event.error:
                print(f"[ERROR] Error event received for {connection_id}: {event.error}")
                await send_error_message(websocket, f"An error occurred: {event.error}")
                break
            
            # Skip events without content or parts
            if not event.content or not event.content.parts:
                continue
            
            # Process the first part
            try:
                part = event.content.parts[0]
                if not part:
                    continue
                
                # Handle text response - only send non-partial responses
                if part.text is not None and not event.partial:
                    print(f"[AGENT]: Text response: {part.text[:50]}... for {connection_id}")
                    
                    # Debug content verification
                    if not part.text.strip():
                        print(f"[WARNING] Received empty text for {connection_id}")
                    
                    # Create message payload
                    message = {
                        "mime_type": "text/plain",
                        "type": "text/plain",
                        "data": part.text,
                        "content": part.text,
                        "role": "model",
                        "partial": False
                    }
                    
                    # Send the message immediately
                    await websocket.send_text(json.dumps(message))
                    has_sent_content = True
                    print(f"[AGENT]: Sent text message for {connection_id}")
                    
                    # Store in conversation memory using the global memory system
                    if HAS_MEMORY and session_id:
                        try:
                            # Store using session_id, not connection_id
                            MEMORY.add_message(session_id, "model", part.text)
                            print(f"[MEMORY]: Stored agent response for session {session_id}")
                            
                            # Extract entities from the response (dates, times, locations)
                            if "appointment" in part.text.lower() or "meeting" in part.text.lower():
                                if "tomorrow" in part.text.lower():
                                    MEMORY.add_entity(session_id, "date", "tomorrow")
                                if "schedule" in part.text.lower() or "create" in part.text.lower():
                                    MEMORY.add_entity(session_id, "action", "create")
                                
                            # Log memory state for debugging
                            summary = get_session_summary(session_id)
                            print(f"[MEMORY]: Session {session_id} summary: {summary}")
                            
                            # Get conversation history
                            history = MEMORY.get_conversation_history(session_id)
                            print(f"[MEMORY]: Conversation has {len(history)} messages")
                        except Exception as mem_err:
                            print(f"[ERROR] Failed to store response in memory: {mem_err}")
                    else:
                        print(f"[WARNING] Cannot store response - memory module unavailable or no session_id for {connection_id}")
                
                # Handle audio response
                elif hasattr(part, 'audio_blob') and part.audio_blob is not None:
                    print(f"[AGENT]: Audio response: {len(part.audio_blob.data)} bytes for {connection_id}")
                    audio_message = {
                        "mime_type": part.audio_blob.mime_type,
                        "type": part.audio_blob.mime_type,
                        "data": base64.b64encode(part.audio_blob.data).decode("utf-8"),
                        "content": "Audio response",
                        "role": "model",
                        "partial": event.partial
                    }
                    await websocket.send_text(json.dumps(audio_message))
                    has_sent_content = True
            except Exception as part_error:
                print(f"[AGENT]: Error processing part: {part_error} for {connection_id}")
                continue
            
            # Handle turn completion
            if event.turn_complete or event.interrupted:
                # Send turn completion marker
                turn_complete_msg = {"turn_complete": True, "interrupted": event.interrupted}
                await websocket.send_text(json.dumps(turn_complete_msg))
                print(f"[AGENT]: Sent turn_complete for {connection_id}")
                break
    
    except WebSocketDisconnect:
        print(f"[INFO] WebSocket disconnected during response for {connection_id}")
    except Exception as e:
        print(f"[ERROR] Error in agent-to-client handler for {connection_id}: {e}")
        import traceback
        traceback.print_exc()
        try:
            await send_error_message(websocket, "An unexpected error occurred. Please try again.")
        except Exception:
            pass
    finally:
        # Clean up the watchdog task if it exists
        if watchdog_task and not watchdog_task.done():
            watchdog_task.cancel()
            try:
                await watchdog_task
            except asyncio.CancelledError:
                pass
        print(f"[AGENT]: Finished agent-to-client messaging for {connection_id}")


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


async def send_error_message(websocket: WebSocket, error_message: str):
    """Send an error message to the client"""
    try:
        error_response = {
            "mime_type": "text/plain",
            "type": "text/plain",
            "data": f"Error: {error_message}",
            "content": f"Error: {error_message}",
            "role": "model",
            "is_error": True
        }
        await websocket.send_text(json.dumps(error_response))
        # Also send turn_complete to ensure the client knows the turn is finished
        await websocket.send_text(json.dumps({"turn_complete": True}))
        print(f"Sent error message to client: {error_message}")
    except Exception as e:
        print(f"Failed to send error message: {e}")


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
