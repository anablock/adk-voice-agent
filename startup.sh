#!/bin/bash
# Decode Google Calendar credentials if available
if [ -n "$GOOGLE_CREDENTIALS_BASE64" ]; then
  echo "$GOOGLE_CREDENTIALS_BASE64" | base64 -d > /app/credentials.json
  echo "Decoded Google Calendar credentials from environment variable"
fi

# Start the application
python -m app.main_audio_config_fix
