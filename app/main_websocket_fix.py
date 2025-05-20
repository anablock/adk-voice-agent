import asyncio
import base64
import json
import os
from pathlib import Path
from typing import AsyncIterable, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
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
API_KEY = os.getenv("API_KEY", "default-dev-key")  # Set a secure API key in production
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
    allow_origins=ALLOWED_ORIGINS,
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
    config = {"response_modalities": [modality], "speech_config": speech_config}

    # Add output_audio_transcription when audio is enabled to get both audio and text
    if is_audio:
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
    try:
        while True:
            async for event in live_events:
                if event is None:
                    continue

                # If the turn complete or interrupted, send it
                if event.turn_complete or event.interrupted:
                    message = {
                        "turn_complete": event.turn_complete,
                        "interrupted": event.interrupted,
                    }
                    await websocket.send_text(json.dumps(message))
                    print(f"[AGENT TO CLIENT]: {message}")
                    continue

                # Read the Content and its first Part
                part = event.content and event.content.parts and event.content.parts[0]
                if not part:
                    continue

                # Make sure we have a valid Part
                if not isinstance(part, types.Part):
                    continue

                # Only send text if it's a partial response (streaming)
                # Skip the final complete message to avoid duplication
                if part.text and event.partial:
                    message = {
                        "mime_type": "text/plain",
                        "data": part.text,
                        "role": "model",
                    }
                    await websocket.send_text(json.dumps(message))
                    print(f"[AGENT TO CLIENT]: text/plain: {part.text}")

                # If it's audio, send Base64 encoded audio data
                is_audio = (
                    part.inline_data
                    and part.inline_data.mime_type
                    and part.inline_data.mime_type.startswith("audio/pcm")
                )
                if is_audio:
                    audio_data = part.inline_data and part.inline_data.data
                    if audio_data:
                        message = {
                            "mime_type": "audio/pcm",
                            "data": base64.b64encode(audio_data).decode("ascii"),
                            "role": "model",
                        }
                        await websocket.send_text(json.dumps(message))
                        print(f"[AGENT TO CLIENT]: audio/pcm: {len(audio_data)} bytes.")
    except WebSocketDisconnect:
        print("WebSocket disconnected during agent-to-client messaging")
    except Exception as e:
        print(f"Error in agent-to-client messaging: {e}")


async def client_to_agent_messaging(
    websocket: WebSocket, live_request_queue: LiveRequestQueue
):
    """Client to agent communication"""
    try:
        while True:
            # Decode JSON message
            message_json = await websocket.receive_text()
            message = json.loads(message_json)
            mime_type = message["mime_type"]
            data = message["data"]
            role = message.get("role", "user")  # Default to 'user' if role is not provided

            # Send the message to the agent
            if mime_type == "text/plain":
                # Send a text message
                content = types.Content(role=role, parts=[types.Part.from_text(text=data)])
                live_request_queue.send_content(content=content)
                print(f"[CLIENT TO AGENT]: {data}")
            elif mime_type == "audio/pcm":
                # Send audio data
                decoded_data = base64.b64decode(data)

                # Send the audio data - note that ActivityStart/End and transcription
                # handling is done automatically by the ADK when input_audio_transcription
                # is enabled in the config
                live_request_queue.send_realtime(
                    types.Blob(data=decoded_data, mime_type=mime_type)
                )
                print(f"[CLIENT TO AGENT]: audio/pcm: {len(decoded_data)} bytes")

            else:
                raise ValueError(f"Mime type not supported: {mime_type}")
    except WebSocketDisconnect:
        print("WebSocket disconnected during client-to-agent messaging")
    except Exception as e:
        print(f"Error in client-to-agent messaging: {e}")


# API Endpoints
@app.get("/")
async def root():
    """API root endpoint"""
    return {"message": "ADK Voice Agent API is running"}

@app.get("/api/status")
async def status(api_key: str = Depends(verify_api_key)):
    """API status endpoint"""
    return {
        "status": "online",
        "active_sessions": len(active_sessions),
        "service": APP_NAME
    }

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    is_audio: str = Query(...),
    api_key: Optional[str] = Query(None),
    x_api_key: Optional[str] = Header(None),
):
    """Client websocket endpoint with API key validation"""
    # Validate API key from header OR query parameter
    provided_api_key = x_api_key or api_key
    
    if provided_api_key != API_KEY:
        print(f"Invalid API key provided: {provided_api_key}")
        await websocket.close(code=1008)  # Policy violation
        return
        
    # Wait for client connection
    await websocket.accept()
    print(f"Client #{session_id} connected, audio mode: {is_audio}")
    
    try:
        # Start agent session or get existing one
        if session_id not in active_sessions:
            live_events, live_request_queue = start_agent_session(
                session_id, is_audio == "true"
            )
        else:
            # Get existing session data
            session_data = active_sessions[session_id]
            live_events = session_data["live_events"]
            live_request_queue = session_data["live_request_queue"]
            
        # Start tasks
        agent_to_client_task = asyncio.create_task(
            agent_to_client_messaging(websocket, live_events)
        )
        client_to_agent_task = asyncio.create_task(
            client_to_agent_messaging(websocket, live_request_queue)
        )
        
        # Wait for both tasks to complete
        await asyncio.gather(agent_to_client_task, client_to_agent_task)
    except WebSocketDisconnect:
        print(f"Client #{session_id} disconnected")
    except Exception as e:
        print(f"Error in websocket endpoint: {e}")
    finally:
        # Don't remove session immediately to allow reconnections
        # In a production app, you might want to add a cleanup job
        # that removes stale sessions after a timeout period
        print(f"Client #{session_id} websocket connection ended")

# For Google Cloud Run
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("app.main_websocket_fix:app", host="0.0.0.0", port=port, reload=False)
