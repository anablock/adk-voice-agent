# Frontend-Backend Communication Documentation

This document provides a detailed overview of how the Next.js frontend communicates with the FastAPI backend in the ADK Voice Agent project. It outlines the expected request formats, response structures, and authentication mechanisms.

## Communication Overview

The frontend communicates with the backend using two primary methods:
1. **HTTP REST API Calls** - For configuration, status checks, and non-streaming operations
2. **WebSocket Connection** - For real-time, bidirectional communication including audio streaming

## Configuration Retrieval

### Endpoint
```
GET /api/voice-assistant/config
```

### Authentication
- Uses Clerk authentication middleware
- Returns 401 if user is not authenticated

### Response Format
```json
{
  "apiUrl": "http://localhost:8081",
  "wsUrl": "ws://localhost:8081/ws",
  "apiKey": "development-key",
  "version": "1.0.0",
  "features": {
    "textToSpeech": true,
    "speechToText": true,
    "calendarIntegration": true
  }
}
```

## Backend Status Check

### Endpoint
```
GET /api/status
```

### Request Headers
```
X-API-Key: <api_key>
```

### Response
- Status code 200 if backend is available
- Error status code if backend is unavailable

## WebSocket Communication

### Connection Establishment

#### WebSocket URL Format
```
{wsUrl}/{session_id}?is_audio={audioModeParam}&api_key={apiKey}
```

Where:
- `wsUrl`: Base WebSocket URL (e.g., ws://localhost:8081/ws)
- `session_id`: Unique identifier for the conversation session (UUID v4)
- `audioModeParam`: Boolean flag indicating if audio mode is enabled ('true' or 'false')
- `apiKey`: API key for authentication

### Message Formats

#### Initial Authentication
```json
{
  "type": "ping",
  "api_key": "development-key"
}
```

#### Text Message to Backend
```json
{
  "mime_type": "text/plain",
  "data": "User's text message",
  "role": "user"
}
```

#### Audio Chunk to Backend
```json
{
  "mime_type": "audio/pcm",
  "data": "base64EncodedAudioData",
  "role": "user"
}
```

#### End of Audio Signal
```json
{
  "mime_type": "text/plain",
  "data": "END_OF_AUDIO",
  "end_of_audio": true,
  "role": "user"
}
```

### Backend Response Formats

#### Welcome Message
```json
{
  "type": "welcome",
  "content": "Hello! How can I help you today?"
}
```

#### Authentication Response
```json
{
  "type": "auth_success"
}
```

#### Text/Content Response
```json
{
  "content": "Response text content",
  "role": "model"
}
```

#### Turn Completion
```json
{
  "turn_complete": true
}
```

#### Transcription Response
```json
{
  "type": "transcription",
  "transcription": "Transcribed text from audio"
}
```

## Important Notes

1. **Audio Format**: The backend expects audio in PCM format, sent as base64-encoded strings.

2. **Streaming Responses**: The backend streams responses, sending partial content that the frontend accumulates into complete messages.

3. **API Key Handling**: The API key is passed both in HTTP headers and as a WebSocket connection parameter.

4. **Session Management**: Each conversation has a unique session ID generated on the frontend using UUID v4.

5. **Error Handling**: The frontend has robust error handling, including automatic reconnection with exponential backoff for WebSocket connections.

## Authentication Flow

1. User authenticates with Clerk in the Next.js application
2. Frontend retrieves configuration including API key via `/api/voice-assistant/config`
3. Frontend uses this API key for all subsequent communication with the backend
4. Backend validates API key on each request/connection

## Common Issues

If the backend is not receiving the expected data, check:

1. **WebSocket URL Format**: Ensure the URL is correctly formatted with session ID and parameters
2. **MIME Types**: Verify that the correct MIME types are being sent (`text/plain` for text, `audio/pcm` for audio)
3. **API Key**: Confirm that the API key is being correctly passed in both HTTP headers and WebSocket parameters
4. **Audio Encoding**: Verify that audio data is properly base64-encoded
5. **JSON Structure**: Ensure that the JSON structure exactly matches what the backend expects

## Request/Response Examples

### Example: Text Conversation

1. Frontend connects to WebSocket
2. Backend sends welcome message
3. User sends text query:
```json
{
  "mime_type": "text/plain",
  "data": "What's on my calendar today?",
  "role": "user"
}
```
4. Backend streams response:
```json
{"content": "Let me check your ", "role": "model"}
{"content": "calendar for today. ", "role": "model"}
{"content": "You have a meeting at 2pm with John.", "role": "model"}
{"turn_complete": true}
```

### Example: Voice Conversation

1. Frontend connects to WebSocket with `is_audio=true`
2. User starts speaking, frontend sends audio chunks:
```json
{"mime_type": "audio/pcm", "data": "base64AudioData1", "role": "user"}
{"mime_type": "audio/pcm", "data": "base64AudioData2", "role": "user"}
{"mime_type": "audio/pcm", "data": "base64AudioData3", "role": "user"}
{"mime_type": "text/plain", "data": "END_OF_AUDIO", "end_of_audio": true, "role": "user"}
```
3. Backend transcribes audio and responds:
```json
{"type": "transcription", "transcription": "What's on my calendar today?"}
{"content": "Let me check your calendar for today. ", "role": "model"}
{"content": "You have a meeting at 2pm with John.", "role": "model"}
{"turn_complete": true}
```
