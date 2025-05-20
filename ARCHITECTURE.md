# ADK Voice Agent Integration Architecture

## Overview

This document outlines the architecture for integrating the ADK Voice Agent (a FastAPI and Google ADK-based voice assistant) into the Anablock AI Answer Engine (a Next.js application) as a new feature. The integration will involve:

1. Deploying the FastAPI backend to Google Cloud Platform (GCP)
2. Creating a React component in the Next.js frontend to interact with the backend
3. Establishing WebSocket communication between the frontend and GCP-hosted backend
4. Setting up authentication and proper environment configuration

## System Architecture

### 1. Component Architecture

```
┌───────────────────────────────────────┐      ┌───────────────────────────────────┐
│                                       │      │                                   │
│  Anablock AI Answer Engine (Next.js)  │      │  ADK Voice Agent (FastAPI)        │
│  ┌────────────────────────────────┐   │      │  ┌─────────────────────────────┐  │
│  │                                │   │      │  │                             │  │
│  │  Voice Assistant Component     │   │      │  │  FastAPI Endpoints          │  │
│  │  - React UI                    │───┼──────┼─▶│  - WebSocket endpoint       │  │
│  │  - WebSocket Client            │   │      │  │  - Authentication routes    │  │
│  │  - Audio Processing            │◀──┼──────┼──│                             │  │
│  └────────────────────────────────┘   │      │  └─────────────────────────────┘  │
│                                       │      │                                   │
│  ┌────────────────────────────────┐   │      │  ┌─────────────────────────────┐  │
│  │                                │   │      │  │                             │  │
│  │  Authentication                │───┼──────┼─▶│  ADK Agent Logic            │  │
│  │  - User session management     │   │      │  │  - Google ADK integration   │  │
│  │                                │   │      │  │  - Gemini 2.0 Flash model   │  │
│  └────────────────────────────────┘   │      │  │                             │  │
│                                       │      │  └─────────────────────────────┘  │
│  ┌────────────────────────────────┐   │      │                                   │
│  │                                │   │      │  ┌─────────────────────────────┐  │
│  │  API Routes                    │   │      │  │                             │  │
│  │  - Configuration endpoints     │───┼──────┼─▶│  Calendar Tools             │  │
│  │  - Status checking             │   │      │  │  - Event operations         │  │
│  │                                │   │      │  │  - Google Calendar API      │  │
│  └────────────────────────────────┘   │      │  │                             │  │
│                                       │      │  └─────────────────────────────┘  │
└───────────────────────────────────────┘      └───────────────────────────────────┘
          Deployed on Vercel                       Deployed on Google Cloud Run
```

### 2. Data Flow

1. **User Interaction Flow**:
   - User interacts with the Voice Assistant component in the Next.js application
   - Voice/text input is captured and processed by the browser
   - Input is sent to the GCP-hosted FastAPI backend via WebSocket
   - Response is received and displayed/played back to the user

2. **Authentication Flow**:
   - User authenticates with the Next.js application
   - Session token is used to authenticate WebSocket connection
   - Backend validates session and establishes WebSocket connection

3. **Calendar Operation Flow**:
   - Calendar requests are processed by the ADK agent
   - Agent uses Calendar Tools to interact with Google Calendar API
   - Results are returned to the frontend via WebSocket

## Backend Architecture (GCP)

### FastAPI Backend Components

1. **WebSocket Endpoint** (`/ws/{session_id}`):
   - Handles real-time communication with the frontend
   - Processes both text and audio input/output

2. **ADK Agent Integration**:
   - Google Agent Development Kit (ADK) with Gemini 2.0 Flash model
   - Processes natural language requests
   - Handles conversation context and state

3. **Calendar Tools**:
   - List events (`list_events`)
   - Create events (`create_event`)
   - Edit events (`edit_event`) 
   - Delete events (`delete_event`)
   - Find free time (`find_free_time`)

4. **Authentication Middleware**:
   - Validates session tokens from the frontend
   - Ensures secure access to the agent

### GCP Deployment

1. **Google Cloud Run**:
   - Containerized deployment of the FastAPI application
   - Autoscaling based on load
   - Secure HTTPS endpoints

2. **Environment Configuration**:
   - GCP Secret Manager for API keys and credentials
   - Environment variables for configuration

3. **API Security**:
   - CORS configuration to accept requests from the Next.js domain
   - API key authentication for non-WebSocket endpoints

## Frontend Architecture (Next.js)

### Voice Assistant Component

1. **User Interface**:
   - Chat interface with message history
   - Voice input/output controls
   - Status indicators (connection, audio processing)

2. **WebSocket Client**:
   - Establishes and maintains connection to the GCP backend
   - Handles reconnection logic
   - Processes incoming/outgoing messages

3. **Audio Processing**:
   - Browser's Web Audio API for recording
   - Audio playback for agent responses
   - PCM encoding/decoding for audio transfer

### Next.js Integration

1. **React Component**:
   - Encapsulated voice assistant component
   - Can be integrated into existing pages or as a standalone feature

2. **API Routes**:
   - `/api/voice-agent/config` - Provides configuration for the frontend
   - `/api/voice-agent/status` - Checks the status of the backend service

3. **Authentication Integration**:
   - Uses existing authentication system from Anablock AI Answer Engine
   - Passes session tokens to the backend for validation

## Authentication and Security

1. **User Authentication**:
   - Leverages existing authentication in Anablock AI Answer Engine
   - Session-based authentication for WebSocket connections

2. **Google Calendar Authentication**:
   - OAuth 2.0 for Google Calendar API
   - Secure storage of refresh tokens in GCP Secret Manager

3. **API Security**:
   - Rate limiting to prevent abuse
   - Input validation for all endpoints
   - Secure WebSocket communication

## Configuration and Environment Setup

1. **GCP Backend Environment Variables**:
   ```
   GEMINI_API_KEY=<your-gemini-api-key>
   GOOGLE_CLIENT_ID=<your-google-client-id>
   GOOGLE_CLIENT_SECRET=<your-google-client-secret>
   ALLOWED_ORIGINS=https://your-nextjs-domain.com
   ```

2. **Next.js Environment Variables**:
   ```
   NEXT_PUBLIC_VOICE_AGENT_API_URL=https://your-gcp-backend-url.run.app
   NEXT_PUBLIC_VOICE_AGENT_WS_URL=wss://your-gcp-backend-url.run.app/ws
   ```

## Implementation Roadmap

1. **Phase 1: Backend Preparation**
   - Modify the FastAPI app for GCP deployment
   - Add authentication and CORS configuration
   - Deploy to Google Cloud Run

2. **Phase 2: Frontend Component**
   - Create React component for the voice assistant
   - Implement WebSocket client and audio processing
   - Add API routes for configuration

3. **Phase 3: Integration and Testing**
   - Integrate the component into the Anablock AI Answer Engine
   - Test end-to-end functionality
   - Performance optimization

4. **Phase 4: Production Deployment**
   - Final security review
   - Production deployment
   - Monitoring and logging setup

## Technical Considerations

1. **WebSocket Performance**: 
   - Implement heartbeat mechanism to keep connections alive
   - Handle reconnection gracefully with exponential backoff

2. **Audio Processing**:
   - Optimize audio packet size for efficient streaming
   - Consider browser compatibility for Web Audio API

3. **Security**:
   - Implement proper token validation for WebSocket connections
   - Secure storage of Google Calendar credentials

4. **Scalability**:
   - Design for horizontal scaling on GCP
   - Consider connection pooling for WebSockets

## Future Enhancements

1. **Offline Capability**:
   - Implement service workers for offline functionality
   - Cache responses for common queries

2. **Additional Integrations**:
   - Expand beyond Google Calendar to other productivity tools
   - Add email integration capabilities

3. **Performance Optimizations**:
   - Implement streaming responses for faster feedback
   - Optimize audio processing for lower latency
