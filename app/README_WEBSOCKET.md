# ADK Voice Agent WebSocket Integration

This document describes the WebSocket integration between the Next.js frontend and the FastAPI backend for the ADK Voice Agent.

## Architecture

The ADK Voice Agent uses a WebSocket connection to enable real-time communication between the frontend and backend:

1. **Frontend (Next.js)**: Connects to the backend via WebSocket, sends user queries, and displays responses.
2. **Backend (FastAPI)**: Processes user queries using Google's Agent Development Kit (ADK) with the Gemini model, interacts with Google Calendar, and sends responses back to the frontend.

## WebSocket Protocol

The WebSocket communication follows this pattern:

1. **Connection**: The frontend connects to the backend with a session ID and audio mode parameter.
2. **Welcome Message**: The backend sends a welcome message upon connection.
3. **User Queries**: The frontend sends user queries as JSON messages.
4. **Agent Responses**: The backend processes queries and sends responses as JSON messages.
5. **Turn Completion**: Each conversational turn is marked with a `turn_complete: true` message.

## Message Formats

### Frontend to Backend

Text query:
```json
{
  "mime_type": "text/plain",
  "data": "What events do I have today?",
  "role": "user"
}
```

Audio query (end marker):
```json
{
  "mime_type": "text/plain",
  "data": "END_OF_AUDIO",
  "end_of_audio": true,
  "role": "user"
}
```

### Backend to Frontend

Text response:
```json
{
  "mime_type": "text/plain",
  "type": "text/plain",
  "data": "You have a meeting at 2 PM with Alex.",
  "content": "You have a meeting at 2 PM with Alex.",
  "role": "model"
}
```

Turn completion:
```json
{
  "turn_complete": true
}
```

## Implementation Options

We provide two backend implementations:

1. **Full ADK Implementation** (`main_audio_config_fix.py`): Integrates with Google's ADK and requires Google API credentials.
2. **Standalone Implementation** (`standalone_websocket.py`): A simplified version that provides reliable responses without requiring Google API credentials.

## Testing

Use the `test_nextjs_integration.py` script to test the WebSocket integration:

```bash
python test_nextjs_integration.py
```

## Environment Variables

Ensure these environment variables are set in the Next.js frontend:

```
VOICE_ASSISTANT_API_URL=http://localhost:8081
VOICE_ASSISTANT_WS_URL=ws://localhost:8081/ws
VOICE_ASSISTANT_API_KEY=development-key
```

## Troubleshooting

If you encounter integration issues:

1. Check that the WebSocket server is running on port 8081
2. Verify that the WebSocket URL formats match in both frontend and backend
3. Check browser console for CORS or WebSocket errors
4. Ensure API keys are properly configured
