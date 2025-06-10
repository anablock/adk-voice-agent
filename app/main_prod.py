#!/usr/bin/env python3
"""
ADK Voice Agent - Production Server
Integrates with Google Calendar for event management and uses a persistent conversation memory.
"""

import os
import sys

# Add the parent directory to the Python path so we can import our app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the main app from the audio config fix module which has our calendar integration
from app.main_audio_config_fix import app

# If this file is run directly, start the server
if __name__ == "__main__":
    import uvicorn
    
    # Get port from environment or default to 8081
    port = int(os.environ.get("PORT", 8081))
    host = os.environ.get("HOST", "0.0.0.0")
    
    print(f"Starting ADK Voice Agent production server on {host}:{port}")
    print(f"Using Google Calendar API with credentials: {os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', 'Not set')}")
    
    # Start the server
    uvicorn.run(
        "app.main_prod:app",
        host=host,
        port=port,
        log_level=os.environ.get("LOG_LEVEL", "info").lower(),
        workers=int(os.environ.get("WORKERS", 1))
    )
