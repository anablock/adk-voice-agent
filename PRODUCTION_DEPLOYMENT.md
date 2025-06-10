# ADK Voice Agent - Production Deployment Guide

This guide outlines the steps for deploying the ADK Voice Agent with Google Calendar integration to a production environment.

## Overview

The ADK Voice Agent is a voice and text-based assistant built using FastAPI and Google's Agent Development Kit (ADK) with Gemini 2.0 Flash model. It supports both text and voice interactions through a web interface and provides calendar operations including:
- Listing calendar events
- Creating new events
- Editing existing events
- Deleting events

## Prerequisites

1. Docker and Docker Compose installed on your production server
2. Google Cloud project with the following APIs enabled:
   - Google Calendar API
   - Google ADK API
   - Gemini API
3. OAuth 2.0 credentials for Google Calendar API
4. Google API Key for Gemini model access

## Production Files

The following files have been prepared for production deployment:

1. `Dockerfile` - Container configuration for the application
2. `docker-compose.yml` - Multi-container deployment configuration
3. `start_prod.sh` - Production startup script using Gunicorn and Uvicorn
4. `requirements.txt` - Updated with production dependencies
5. `app/calendar_integration.py` - Google Calendar API integration
6. `app/conversation_memory.py` - Persistent conversation memory
7. `app/main_audio_config_fix.py` - Main application with WebSocket support

## Deployment Steps

### 1. Prepare Environment Variables

Create a `.env` file with the following variables:

```
# Required API Keys
GOOGLE_API_KEY=your_gemini_api_key
API_KEY=your_production_api_key

# Google Calendar Settings
GOOGLE_CALENDAR_ID=primary

# Security Settings
ALLOWED_ORIGINS=https://your-production-domain.com

# Logging
LOG_LEVEL=INFO
```

### 2. Prepare Google Calendar Credentials

1. Place your OAuth 2.0 credentials JSON file at the root of the project as `credentials.json`
2. This file will be mounted into the Docker container

### 3. Create Data Directory

```bash
mkdir -p data
```

### 4. Build and Deploy the Container

```bash
# Build the Docker image
docker-compose build

# Start the service in detached mode
docker-compose up -d
```

### 5. Initialize Calendar Authentication

The first time you run the container, you'll need to authenticate with Google Calendar:

```bash
# Run the setup script inside the container
docker-compose exec adk-voice-agent python setup_calendar_auth.py
```

This will:
1. Open a browser window for OAuth authentication
2. Store the token for future use

### 6. Verify Deployment

1. Check if the container is running:
   ```bash
   docker-compose ps
   ```

2. Check the logs:
   ```bash
   docker-compose logs -f
   ```

3. Test the API endpoint:
   ```bash
   curl http://localhost:8081/status
   ```

## Production Security Considerations

1. **API Key Protection**: Ensure the API key is kept secure and not exposed in client-side code
2. **HTTPS**: Configure SSL/TLS for all communication
3. **Regular Updates**: Keep all dependencies up to date
4. **Monitoring**: Set up monitoring and alerting for the service
5. **Rate Limiting**: Consider implementing rate limiting to prevent abuse

## Scaling Considerations

For higher load scenarios:
1. Increase the number of Gunicorn workers in `start_prod.sh`
2. Use a load balancer to distribute traffic across multiple container instances
3. Consider using a managed Kubernetes service for orchestration

## Backup and Recovery

1. **Calendar Token**: The OAuth token is stored in `~/.credentials/calendar_token.json` and mounted as a volume
2. **Conversation Memory**: Stored in the `/app/data` directory, which is mounted as a volume
3. **Regular Backups**: Implement regular backups of these volumes

## Troubleshooting

1. **Calendar Authorization Issues**:
   - Check that the credentials.json file is correctly mounted
   - Verify the OAuth token is valid and not expired
   - Run the setup_calendar_auth.py script again if needed

2. **API Connection Issues**:
   - Verify the GOOGLE_API_KEY is correctly set
   - Check that all required APIs are enabled in Google Cloud Console

3. **Container Startup Issues**:
   - Check the container logs: `docker-compose logs -f`
   - Verify all environment variables are correctly set

## Monitoring

Configure monitoring for:
1. Container health (using the built-in healthcheck)
2. API response times
3. Error rates
4. Memory and CPU usage

---

For additional help or questions, please refer to the main project documentation or contact the development team.
